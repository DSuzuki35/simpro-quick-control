'use strict';
const $=id=>document.getElementById(id);
const overlay=new URLSearchParams(location.search).has('overlay');
document.body.classList.toggle('overlay',overlay);
let token='',state=null,structure='',bindingSignature='',busy=false,toastTimer;
const labels={increase:'Increase selected',decrease:'Decrease selected',next:'Next setting',previous:'Previous setting',show:'Show popup'};
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500)}
async function api(path,data){
 const r=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-Control-Token':token,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 const body=await r.json();if(!r.ok)throw new Error(body.error||'Request failed');return body;
}
async function act(path,data={}){try{await api(path,data);await refresh()}catch(e){toast(e.message)}}
function text(node,value){if(node.textContent!==String(value))node.textContent=value}
function display(setting,value){return setting.choices?setting.choices[value]??'—':String(value??'—')+setting.unit}
function choose(key){return act('config',{selected:key})}
function cycle(direction){if(!state)return;const keys=state.config.cycle.filter(k=>k in state.values);if(!keys.length)return;let i=keys.indexOf(state.config.selected);choose(keys[(i+direction+keys.length)%keys.length])}
async function adjust(direction){if(busy||!state)return;busy=true;try{await act('adjust',{key:state.config.selected,direction})}finally{busy=false}}
function tab(name){document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id===name))}
function makeBinding(action){
 const wrap=document.createElement('div');wrap.className='binding-action';
 const learn=document.createElement('button');learn.className='learn-button';learn.dataset.action=action;learn.textContent='Learn';learn.onclick=()=>act('learn',{action});
 const clear=document.createElement('button');clear.className='clear-button';clear.textContent='×';clear.title='Clear assignment';clear.setAttribute('aria-label','Clear '+(labels[action]||action));
 clear.onclick=()=>{const bindings={...state.config.bindings};delete bindings[action];act('config',{bindings})};wrap.append(learn,clear);return wrap;
}
function build(settings){
 $('settingList').replaceChildren();$('dedicatedBindings').replaceChildren();
 let group='';for(const setting of settings){
  if(group!==setting.group){group=setting.group;const heading=document.createElement('div');heading.className='setting-group';heading.textContent=group;$('settingList').append(heading)}
  const row=document.createElement('button');row.className='setting-row';row.dataset.key=setting.key;row.onclick=()=>choose(setting.key);
  const label=document.createElement('span');label.textContent=setting.label;const val=document.createElement('strong');val.dataset.value=setting.key;row.append(label,val);$('settingList').append(row);
  const tr=document.createElement('tr'),name=document.createElement('td');name.textContent=setting.label;
  const stepCell=document.createElement('td'),step=document.createElement('input');step.type='number';step.min='1';step.max=setting.choices?'1':'100';step.dataset.step=setting.key;step.setAttribute('aria-label',setting.label+' step');step.value=state.config.steps[setting.key]||setting.step;
  step.onchange=()=>{const n=Number(step.value);if(!Number.isInteger(n)||n<1||n>100){toast('Use a whole-number step from 1 to 100.');step.value=state.config.steps[setting.key]||setting.step;return}act('config',{steps:{...state.config.steps,[setting.key]:n}})};
  if(setting.choices)step.disabled=true;stepCell.append(step);
  const minus=document.createElement('td'),plus=document.createElement('td');minus.append(makeBinding(setting.key+':decrease'));plus.append(makeBinding(setting.key+':increase'));
  const cycleCell=document.createElement('td'),check=document.createElement('input');check.type='checkbox';check.dataset.cycle=setting.key;check.setAttribute('aria-label','Include '+setting.label+' in cycle');check.checked=state.config.cycle.includes(setting.key);
  check.onchange=()=>{let keys=state.config.cycle.filter(k=>k!==setting.key);if(check.checked)keys.push(setting.key);if(!keys.length){check.checked=true;return toast('Keep at least one setting in the cycle.')}act('config',{cycle:keys})};cycleCell.append(check);tr.append(name,stepCell,minus,plus,cycleCell);$('dedicatedBindings').append(tr);
 }
}
function render(){
 const s=state;const connected=s.connected;
 text($('connection'),connected?'SimPro connected':'SimPro offline');$('connection').classList.toggle('connected',connected);
 $('error').hidden=!s.error&&!s.input_error;text($('error'),s.error||s.input_error||'');
 text($('rigName'),connected?`${s.device} · ${s.max_torque} Nm · ${s.preset_name}`:'Keep SimPro Manager open and connect your wheelbase.');
 text($('enable'),s.enabled?'Controls enabled · Pause':'Enable controls');$('enable').classList.toggle('on',s.enabled);$('enable').disabled=!connected;
 text($('live'),s.enabled?'CONTROLS LIVE':connected?'CONTROLS PAUSED':'SIMPRO OFFLINE');$('live').classList.toggle('on',s.enabled);
 const sig=JSON.stringify(s.settings.map(x=>x.key));if(!overlay&&sig!==structure){structure=sig;build(s.settings)}
 const selected=s.settings.find(x=>x.key===s.config.selected);if(selected){
  const value=s.values[selected.key];text($('selectedLabel'),selected.label);text($('selectedGroup'),selected.group.toUpperCase());
  text($('value'),selected.choices?selected.choices[value]:value);text($('unit'),selected.choices?'':selected.unit);
  let secondary=selected.key==='total_force'?`${(value*s.max_torque/100).toFixed(2)} Nm · ${s.values.reverse?'reversed direction':'base output limit'}`:selected.choices?'Use + / − to choose':`Live value · ${s.preset_name}`;
  if(!connected)secondary='Disconnected — values may be stale';text($('secondary'),secondary);
  $('meterFill').style.width=Math.max(0,Math.min(100,100*(value-selected.min)/(selected.max-selected.min)))+'%';
  text($('rangeMin'),selected.choices?selected.choices[0]:selected.min+selected.unit);text($('rangeMax'),selected.choices?selected.choices.at(-1):selected.max+selected.unit);
  text($('stepLabel'),selected.choices?'select':`${(s.config.steps[selected.key]||selected.step)*(s.multiplier||1)}${selected.unit} / click${s.multiplier>1?' · ×'+s.multiplier:''}`);text($('preset'),s.preset_name);
 }
 $('minus').disabled=$('plus').disabled=!s.enabled||!connected;
 if(overlay)return;
 $('startWindows').checked=!!s.startup_enabled;$('autoEnable').checked=!!s.config.auto_enable;
 const compat=s.compatibility;text($('compatibility'),compat?`SimPro ${compat.detected} · ${compat.experimental?'Experimental compatibility — optimized and tested with '+compat.tested:'Tested version'}`:'Optimized and tested with SimPro 3.2.4.13771. Other versions are experimental.');
 text($('settingCount'),s.settings.length+' controls');
 document.querySelectorAll('.setting-row').forEach(row=>{row.classList.toggle('selected',row.dataset.key===s.config.selected);const setting=s.settings.find(x=>x.key===row.dataset.key);text(row.querySelector('strong'),display(setting,s.values[setting.key]))});
 const bs=JSON.stringify([s.config,s.learning]);if(bs!==bindingSignature){bindingSignature=bs;
  document.querySelectorAll('[data-action]').forEach(b=>{const binding=s.config.bindings[b.dataset.action];b.classList.toggle('assigned',!!binding);text(b,s.learning===b.dataset.action?'Listening…':binding?`Button ${binding.button+1}`:'Learn');b.title=binding?binding.device.split('|').at(-1):'Press a USB button or turn an encoder'});
  document.querySelectorAll('[data-step]').forEach(i=>{if(document.activeElement!==i)i.value=s.config.steps[i.dataset.step]||s.settings.find(x=>x.key===i.dataset.step)?.step||1});
  document.querySelectorAll('[data-cycle]').forEach(i=>i.checked=s.config.cycle.includes(i.dataset.cycle));
  $('acceleration').checked=!!s.config.acceleration;$('mode').value=s.config.mode;const delay=s.config.hide_after;$('hideAfter').value=[0,3,5,10].includes(delay)?String(delay):'custom';$('customDelayLabel').hidden=$('hideAfter').value!=='custom';if(document.activeElement!==$('customDelay'))$('customDelay').value=delay||15;
 }
 $('learning').hidden=!s.learning;text($('learnText'),s.learning?`Listening for ${labels[s.learning]||s.learning.replace(':',' · ')} — press a control within 20 seconds.`:'');
 const ds=JSON.stringify(s.devices);if($('devices').dataset.signature!==ds){$('devices').dataset.signature=ds;$('devices').replaceChildren();for(const d of s.devices){const row=document.createElement('div');row.className='device';const name=document.createElement('strong');name.textContent=d.name;const info=document.createElement('span');info.textContent=d.ambiguous?'Identical devices — inputs ignored':`${d.buttons} buttons`;row.append(name,info);$('devices').append(row)}if(!s.devices.length)$('devices').textContent='No USB joysticks detected.'}
 text($('lastInput'),s.last_input||'Waiting for a button press.');
}
async function refresh(){try{state=await api('state');render()}catch(e){text($('connection'),'Controller unavailable');$('connection').classList.remove('connected');$('minus').disabled=$('plus').disabled=true;}}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
if(!overlay)for(const action of Object.keys(labels)){const card=document.createElement('div');card.className='bind-card';const title=document.createElement('div');title.className='bind-title';title.textContent=labels[action];card.append(title,makeBinding(action));$('sharedBindings').append(card)}
$('enable').onclick=()=>act('enable',{enabled:!state.enabled});$('minus').onclick=()=>adjust(-1);$('plus').onclick=()=>adjust(1);$('previous').onclick=()=>cycle(-1);$('next').onclick=()=>cycle(1);
$('mode').onchange=()=>act('config',{mode:$('mode').value});$('cancelLearn').onclick=()=>act('learn',{action:null});
$('acceleration').onchange=()=>act('config',{acceleration:$('acceleration').checked});
$('quitController').onclick=()=>act('quit');
$('startWindows').onchange=()=>act('startup',{enabled:$('startWindows').checked});
$('autoEnable').onchange=()=>act('config',{auto_enable:$('autoEnable').checked});
$('hideAfter').onchange=()=>{const custom=$('hideAfter').value==='custom';$('customDelayLabel').hidden=!custom;if(!custom)act('config',{hide_after:Number($('hideAfter').value)})};
$('applyDelay').onclick=()=>{const delay=Number($('customDelay').value);if(!Number.isFinite(delay)||delay<1||delay>600)return toast('Choose a delay from 1 to 600 seconds.');act('config',{hide_after:delay})};
$('showMenu').onclick=$('previewPopup').onclick=()=>act('show');$('overlaySettings').onclick=()=>act('open-settings');$('overlayHide').onclick=()=>act('hide');
async function poll(){await refresh();setTimeout(poll,document.hidden?2000:overlay&&state&&!state.menu_visible?1000:300)}
async function start(){try{token=(await fetch('/api/session').then(r=>r.json())).token;poll()}catch(e){toast('Could not connect to the local controller.')}}
start();
