// Build public client only. Private server credentials never enter this output.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),web=path.join(root,'web');
const core=fs.readFileSync(path.join(web,'SurveyCore.html'),'utf8');
const template=fs.readFileSync(path.join(web,'inspection.html'),'utf8');
const page=template.replace("<?!= include_('Core'); ?>",core).replace('<!--INSPECTION_TOOLS-->','<script src="inspection-tools.js"></script>');
if(page.includes('<?!=')||page.includes('ADMIN_EMAIL_')||/[a-z0-9._%+-]+@gmail\.com/i.test(page))throw Error('Unresolved or private source in public page');
fs.writeFileSync(path.join(root,'inspection.html'),page);
for(const name of ['inspection-tools.js','docx.umd.js','tesseract.min.js'])fs.copyFileSync(path.join(web,name),path.join(root,name));
console.log('Built public inspection workspace (session-only)');
