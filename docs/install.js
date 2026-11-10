(function(){
'use strict';
let promptEvent=null;
const button=document.querySelector('#install-app'),notice=document.querySelector('#connection-notice');
function connection(){if(notice)notice.hidden=navigator.onLine;}
window.addEventListener('online',connection);window.addEventListener('offline',connection);connection();
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();promptEvent=e;if(button)button.hidden=false;});
window.addEventListener('appinstalled',()=>{promptEvent=null;if(button)button.hidden=true;});
if(button)button.addEventListener('click',async()=>{if(!promptEvent)return;const event=promptEvent;promptEvent=null;button.hidden=true;try{await event.prompt();await event.userChoice;}catch(_){/* The browser keeps its own installation command available. */}});
})();
