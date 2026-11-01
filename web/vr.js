'use strict';
const el=id=>document.getElementById(id),always=new URLSearchParams(location.search).get('always')==='1';
let token='',offlineSince=0,lastDelay=5;
function disconnected(){
 if(!offlineSince)offlineSince=Date.now();
 el('label').textContent='SimPro unavailable';
 el('readout').classList.add('offline');el('status').className='';el('status').textContent='OFFLINE';
 el('value').textContent='—';el('unit').textContent='';el('secondary').textContent='';el('bar').style.width='0%';
 el('readout').classList.toggle('idle',!always&&lastDelay>0&&Date.now()-offlineSince>lastDelay*1000);
}
async function poll(){
 try{
  if(!token){const r=await fetch('/api/session');if(!r.ok)throw Error();token=(await r.json()).token;}
  const response=await fetch('/api/state',{headers:{'X-Control-Token':token}});
  if(!response.ok){token='';throw Error();}
  const s=await response.json();lastDelay=s.config.hide_after;
  if(!s.connected){disconnected();el('readout').classList.toggle('idle',!always&&!s.menu_visible);return;}
  offlineSince=0;const setting=s.settings.find(x=>x.key===s.config.selected);if(!setting)throw Error();
  const v=s.values[setting.key];el('label').textContent=setting.label;
  el('status').textContent=s.enabled?`LIVE${s.multiplier>1?' ×'+s.multiplier:''}`:'PAUSED';el('status').className=s.enabled?'live':'';
  el('value').textContent=setting.choices?setting.choices[v]:v;el('unit').textContent=setting.choices?'':setting.unit;
  el('secondary').textContent=setting.key==='total_force'?`${(v*s.max_torque/100).toFixed(1)} Nm`:'';
  el('bar').style.width=Math.max(0,Math.min(100,(v-setting.min)/(setting.max-setting.min)*100))+'%';
  el('readout').classList.remove('offline');el('readout').classList.toggle('idle',!always&&!s.menu_visible);
 }catch{disconnected();}finally{setTimeout(poll,document.hidden?2000:200);}
}
poll();
