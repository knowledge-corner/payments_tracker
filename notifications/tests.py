import datetime
import json
import os
from decimal import Decimal
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.testing import make_admin, make_case, make_doctor, make_hospital
from payments.models import Payment

from . import webpush
from .models import NotificationPreference, NotifiedCase, PushSubscription, SentNotification
from .services import run_for_user


def subscription_keys():
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return webpush.b64url_encode(pub), webpush.b64url_encode(os.urandom(16))


def at_hour(hour, day=None):
    day = day or timezone.localdate()
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, 5)))


class WebPushCryptoTests(TestCase):
    def test_rfc8291_test_vector(self):
        body = webpush.encrypt(
            b"When I grow up, I want to be a watermelon",
            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
            "BTBZMqHH6r4Tts7J_aSIgg",
            _as_private=webpush.load_private_key("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"),
            _salt=webpush.b64url_decode("DGv6ra1nlYgDCS1FRnbzlw"),
        )
        self.assertEqual(
            webpush.b64url_encode(body),
            "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN",
        )

    def test_vapid_header_shape(self):
        priv, pub = webpush.generate_vapid_keys()
        header = webpush.vapid_headers("https://web.push.apple.com/abc", priv, pub, "mailto:a@b.c")["Authorization"]
        self.assertTrue(header.startswith("vapid t="))
        token = header.split("t=")[1].split(",")[0]
        claims = json.loads(webpush.b64url_decode(token.split(".")[1]))
        self.assertEqual(claims["aud"], "https://web.push.apple.com")


@mock.patch("notifications.push.webpush.send", return_value=201)
class NotificationFlowTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.user = self.doctor.user
        self.hospital = make_hospital("Ruby Hall Clinic")
        p256dh, auth = subscription_keys()
        self.sub = PushSubscription.objects.create(user=self.user, endpoint="https://fcm.googleapis.com/fcm/send/x",
                                                   p256dh=p256dh, auth=auth)

    def no_weekly_report(self):
        prefs = NotificationPreference.for_user(self.user)
        prefs.weekly_report = False
        prefs.save()

    def titles(self, send_mock):
        return [c.args[3]["title"] for c in send_mock.call_args_list]

    def test_reminder_on_expected_date_and_summary_once(self, send):
        self.no_weekly_report()  # keep the test independent of the weekday it runs on
        today = timezone.localdate()
        make_case(self.doctor, self.hospital, days_ago=40, fee=4500)   # default 30-day date passed
        make_case(self.doctor, self.hospital, days_ago=1, fee=3000, due_date=today)  # expected today
        make_case(self.doctor, self.hospital, days_ago=8, fee=2000)    # not yet: no 7-day reminder any more
        run_for_user(self.user, at_hour(9))
        titles = self.titles(send)
        self.assertEqual(titles, ["Payment reminder: 2 cases to follow up", "Good morning - today's payments"])
        send.reset_mock()
        run_for_user(self.user, at_hour(15))  # later the same day: nothing new
        self.assertEqual(send.call_count, 0)
        self.assertEqual(NotifiedCase.objects.count(), 2)

    def test_case_due_tomorrow_reminds_tomorrow_morning(self, send):
        """The reported scenario: case added today, expected payment date tomorrow."""
        self.no_weekly_report()
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        make_case(self.doctor, self.hospital, fee=5000, due_date=tomorrow)
        run_for_user(self.user, at_hour(9))
        self.assertEqual(send.call_count, 0)
        run_for_user(self.user, at_hour(8, tomorrow))
        self.assertEqual(send.call_count, 0)  # before the chosen time
        run_for_user(self.user, at_hour(9, tomorrow))
        self.assertIn("Payment reminder: 1 case to follow up", self.titles(send))

    def test_respects_hour_and_switches(self, send):
        self.no_weekly_report()
        make_case(self.doctor, self.hospital, days_ago=40)
        run_for_user(self.user, at_hour(7))
        self.assertEqual(send.call_count, 0)  # before the 9 AM preference
        prefs = NotificationPreference.for_user(self.user)
        prefs.daily_summary = False
        prefs.save()
        run_for_user(self.user, at_hour(9))
        self.assertEqual(self.titles(send), ["Payment reminder: 1 case to follow up"])
        prefs.push_enabled = False
        prefs.save()
        send.reset_mock()
        run_for_user(self.user, at_hour(10, timezone.localdate() + datetime.timedelta(days=8)))
        self.assertEqual(send.call_count, 0)

    def test_weekly_report_on_monday(self, send):
        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())
        make_case(self.doctor, self.hospital, days_ago=(today - monday).days + 3, fee=5000)
        run_for_user(self.user, at_hour(9, monday))
        self.assertTrue(any(t.startswith("Last week") for t in self.titles(send)))

    def test_payment_by_admin_notifies_doctor_but_own_payment_does_not(self, send):
        case = make_case(self.doctor, self.hospital, fee=5000)
        with self.captureOnCommitCallbacks(execute=True):
            Payment.objects.create(case=case, amount=Decimal("1000"), created_by=self.user)
        self.assertEqual(send.call_count, 0)
        with self.captureOnCommitCallbacks(execute=True):
            Payment.objects.create(case=case, amount=Decimal("2000"), created_by=make_admin())
        self.assertEqual(self.titles(send), ["Payment recorded"])
        self.assertIn("₹2,000", send.call_args.args[3]["body"])

    def test_gone_subscription_is_removed(self, send):
        send.side_effect = webpush.PushGone(410)
        make_case(self.doctor, self.hospital, days_ago=40)
        run_for_user(self.user, at_hour(9))
        self.assertFalse(PushSubscription.objects.exists())
        self.assertFalse(SentNotification.objects.exists())

    def test_no_device_means_nothing_marked(self, send):
        self.sub.delete()
        make_case(self.doctor, self.hospital, days_ago=40)
        run_for_user(self.user, at_hour(9))
        self.assertEqual(NotifiedCase.objects.count(), 0)  # will be sent once a device is added


@mock.patch("notifications.push.webpush.send", return_value=201)
class NotificationViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.client.force_login(self.doctor.user)

    def test_subscribe_unsubscribe_and_test(self, send):
        p256dh, auth = subscription_keys()
        data = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": p256dh, "auth": auth}}
        r = self.client.post(reverse("notifications:subscribe"), json.dumps(data), content_type="application/json")
        self.assertEqual(r.json()["devices"], 1)
        r = self.client.post(reverse("notifications:test"), follow=True)
        self.assertContains(r, "Test notification sent to 1 device")
        self.assertContains(r, "Recent notifications")
        self.client.post(reverse("notifications:unsubscribe"), json.dumps({"endpoint": data["endpoint"]}),
                         content_type="application/json")
        self.assertFalse(PushSubscription.objects.exists())

    def test_rejects_bad_subscription(self, send):
        r = self.client.post(reverse("notifications:subscribe"), json.dumps({"endpoint": "http://evil"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_save_preferences(self, send):
        r = self.client.post(reverse("notifications:settings"), {
            "push_enabled": "on", "daily_summary": "on", "summary_hour": "8",
        })
        self.assertRedirects(r, reverse("notifications:settings"))
        prefs = NotificationPreference.for_user(self.doctor.user)
        self.assertTrue(prefs.daily_summary)
        self.assertFalse(prefs.followup_reminders)
        self.assertEqual(prefs.summary_hour, 8)

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    def test_public_key_endpoint(self, send):
        key = self.client.get(reverse("notifications:key")).json()["publicKey"]
        self.assertEqual(len(webpush.b64url_decode(key)), 65)
        self.assertEqual(key, self.client.get(reverse("notifications:key")).json()["publicKey"])  # stable


class CheckNotificationsCommandTests(TestCase):
    def test_reports_problems_and_due_reminders(self):
        import io

        from django.core.management import call_command

        doctor = make_doctor()
        make_case(doctor, make_hospital("Ruby Hall Clinic"), days_ago=1, due_date=timezone.localdate())
        out = io.StringIO()
        call_command("check_notifications", doctor.user.username, stdout=out)
        text = out.getvalue()
        self.assertIn("Devices turned on: 0", text)
        self.assertIn("PROBLEM: No device", text)
        self.assertIn("payment reminders due today: 1", text)
        self.assertIn("Ruby Hall Clinic", text)
