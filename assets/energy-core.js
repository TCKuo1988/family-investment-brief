const TYPES=['trips','charges','odometers','expenses','bills','observations'];
function sum(rows,key){return rows.reduce((n,r)=>n+(typeof r[key]==='number'&&Number.isFinite(r[key])?r[key]:0),0)}
function efficiency(rows){const valid=rows.filter(r=>r.distance_km>0&&r.energy_kwh>0);return valid.length?sum(valid,'distance_km')/sum(valid,'energy_kwh'):null}
function finite(value,label,min=0,max=Infinity){if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max)throw Error(label+'數值無效')}
function validateRecord(type,r){
 if(!TYPES.includes(type))throw Error('未知紀錄類型');
 if(typeof r.id!=='string'||!r.id||r.id.length>160)throw Error('紀錄ID無效');
 if(type!=='observations'){if(!/^\d{4}-\d{2}-\d{2}$/.test(r.date||'')||Number.isNaN(Date.parse(r.date))||new Date(r.date).toISOString().slice(0,10)!==r.date)throw Error('日期無效')}
 if(type!=='bills'&&!['MODEL_Y','EX30','UNASSIGNED'].includes(r.vehicle_id))throw Error('車輛無效');
 if(type==='trips'){finite(r.distance_km,'里程',0.01);if(r.energy_kwh!==null)finite(r.energy_kwh,'行車耗電',0.01)}
 if(type==='charges'){if(!['home','external'].includes(r.location))throw Error('充電位置無效');if(r.charger_kwh!==null)finite(r.charger_kwh,'充電量',0.001);if(r.duration_minutes!=null)finite(r.duration_minutes,'時長');if(r.actual_cost_twd!==null&&r.actual_cost_twd!==undefined)finite(r.actual_cost_twd,'費用');for(const k of ['soc_start','soc_end'])if(r[k]!=null)finite(r[k],'SOC',0,100)}
 if(type==='expenses'){finite(r.amount_twd,'金額');if(r.category==='停車')throw Error('停車費應引用既有記帳，避免重複記帳')}
 if(type==='odometers')finite(r.odometer_km,'儀表里程');
 if(type==='bills'){finite(r.meter_kwh,'電表度數',0.001);finite(r.amount_twd,'帳單金額');if(!r.period_start||!r.period_end||r.period_start>r.period_end||![r.period_start,r.period_end].every(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&!Number.isNaN(Date.parse(d))&&new Date(d).toISOString().slice(0,10)===d))throw Error('帳單期間無效')}
 return r;
}
function validateData(d){if(d?.schema_version!==2)throw Error('需要版本2備份檔');for(const t of TYPES){if(!Array.isArray(d[t]))throw Error('缺少資料表：'+t);const ids=new Set();for(const r of d[t]){validateRecord(t,r);if(ids.has(r.id))throw Error('檔案內有重複ID');ids.add(r.id)}}return d}
function active(rows){return rows.filter(r=>!r.archived)}
function chargeSignature(r){return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(r.start_time||'')&&Number.isFinite(Date.parse(r.start_time))&&r.charger_kwh!=null?[Date.parse(r.start_time),r.location,r.charger_kwh].join('|'):null}
function mergeData(old,incoming){validateData(incoming);const next=JSON.parse(JSON.stringify(old));let added=0,skipped=0;for(const t of TYPES){const ids=new Set(next[t].map(r=>r.id));const signatures=new Set(t==='charges'?next[t].map(chargeSignature).filter(Boolean):[]);for(const r of incoming[t]){const signature=t==='charges'?chargeSignature(r):null;if(ids.has(r.id)||(signature&&signatures.has(signature))){skipped++;continue}next[t].push(r);ids.add(r.id);if(signature)signatures.add(signature);added++}}return {data:next,added,skipped}}
function billAllocation(bill,charges,baseline=0){
 finite(baseline,'基本負載');const rows=active(charges).filter(r=>r.location==='home'&&r.date>=bill.period_start&&r.date<=bill.period_end&&r.charger_kwh!=null);
 const quantities=Object.fromEntries(['MODEL_Y','EX30','UNASSIGNED'].map(id=>[id,sum(rows.filter(r=>r.vehicle_id===id),'charger_kwh')]));const total=Object.values(quantities).reduce((a,b)=>a+b,0);
 const average=bill.amount_twd/bill.meter_kwh;
 return {quantities,total,average,allocations:Object.fromEntries(Object.entries(quantities).map(([id,k])=>[id,k*average])),difference_kwh:bill.meter_kwh-total,baseline_cost:baseline*average,residual_cost:(bill.meter_kwh-total-baseline)*average,warning:total+baseline>bill.meter_kwh};
}
function parseCSV(text){const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()))rows.push(row);row=[];cell=''}else cell+=c}if(quoted)throw Error('CSV引號未關閉');row.push(cell);if(row.some(v=>v.trim()))rows.push(row);return rows}
