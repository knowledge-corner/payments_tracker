const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + __dirname + '/pricing.html'); await p.waitForTimeout(500);
  await p.pdf({ path: __dirname + '/../Team_Anesthesia_Running_Costs.pdf', format: 'A4', printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-size:8px;color:#888;width:100%;text-align:center;font-family:Arial">Team Anesthesia - Running costs · Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
    margin: { top: '14mm', bottom: '16mm', left: '13mm', right: '13mm' } });
  await b.close();
})();
