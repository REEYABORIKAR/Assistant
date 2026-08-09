import { useEffect } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { ProjectsPage } from './pages/ProjectsPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { DashboardPage } from './pages/DashboardPage';
import { SettingsPage } from './pages/SettingsPage';

function ChatOptions() {
  useEffect(() => {
    const addOptions = () => document.querySelectorAll<HTMLButtonElement>('button.w-full.truncate').forEach((button, index) => {
      if (button.parentElement?.querySelector('[data-options]')) return;
      const projectId = location.pathname.match(/project\/([^/]+)/)?.[1];
      const chats = (JSON.parse(localStorage.getItem('refyne.chats') || '[]') as {id:string;project_id:string;title:string;updated_at:string}[]).filter(c=>c.project_id===projectId).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
      const chat = chats[index]; if (!chat) return;
      const parent = button.parentElement as HTMLElement; parent.style.position='relative'; button.style.paddingRight='2.5rem';
      const dots=document.createElement('button'); dots.dataset.options='true'; dots.textContent='⋮'; dots.className='absolute right-1 top-1 rounded p-1 text-slate-500 hover:bg-slate-100'; dots.setAttribute('aria-label','Conversation options');
      dots.onclick=e=>{e.stopPropagation(); parent.querySelector('[data-menu]')?.remove(); const menu=document.createElement('div'); menu.dataset.menu='true'; menu.className='absolute right-1 top-9 z-20 w-36 rounded-lg border bg-white p-1 shadow-lg'; const rename=document.createElement('button'); rename.textContent='Rename'; rename.className='block w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50'; const remove=document.createElement('button'); remove.textContent='Delete'; remove.className='block w-full rounded px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50'; menu.append(rename,remove); parent.append(menu);
        rename.onclick=()=>{menu.remove(); button.classList.add('hidden');dots.classList.add('hidden');const form=document.createElement('form');form.className='flex gap-1 p-1';const input=document.createElement('input');input.value=chat.title;input.className='min-w-0 flex-1 rounded border px-2 py-1 text-sm';const save=document.createElement('button');save.textContent='Save';save.className='rounded bg-indigo-600 px-2 text-xs text-white';form.append(input,save);parent.append(form);input.focus();form.onsubmit=x=>{x.preventDefault();if(!input.value.trim())return;const all=JSON.parse(localStorage.getItem('refyne.chats')||'[]');localStorage.setItem('refyne.chats',JSON.stringify(all.map((c:{id:string})=>c.id===chat.id?{...c,title:input.value.trim(),updated_at:new Date().toISOString()}:c)));location.reload();};};
        remove.onclick=()=>{menu.innerHTML='<p class="px-2 py-1 text-xs text-slate-500">Delete this chat?</p>';const yes=document.createElement('button');yes.textContent='Delete';yes.className='block w-full rounded px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50';const no=document.createElement('button');no.textContent='Cancel';no.className='block w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50';menu.append(yes,no);no.onclick=()=>menu.remove();yes.onclick=()=>{const all=JSON.parse(localStorage.getItem('refyne.chats')||'[]');localStorage.setItem('refyne.chats',JSON.stringify(all.filter((c:{id:string})=>c.id!==chat.id)));const messages=JSON.parse(localStorage.getItem('refyne.messages')||'[]');localStorage.setItem('refyne.messages',JSON.stringify(messages.filter((m:{chat_id:string})=>m.chat_id!==chat.id)));location.assign(`/app/project/${projectId}`);};};}; parent.append(dots);
    });
    const observer=new MutationObserver(addOptions);observer.observe(document.body,{childList:true,subtree:true});addOptions();return()=>observer.disconnect();
  },[]); return null;
}
function Shell(){const{loading}=useAuth();return loading?<div className="grid min-h-screen place-items-center">Loading Refyne…</div>:<AppLayout><ChatOptions/><Outlet/></AppLayout>}
export default function App(){return <AuthProvider><Routes><Route path="/app" element={<Shell/>}><Route index element={<Navigate to="projects" replace/>}/><Route path="projects" element={<ProjectsPage/>}/><Route path="project/:projectId" element={<WorkspacePage/>}/><Route path="project/:projectId/chat/:chatId" element={<WorkspacePage/>}/><Route path="project/:projectId/dashboard" element={<DashboardPage/>}/><Route path="settings" element={<SettingsPage/>}/></Route><Route path="*" element={<Navigate to="/app/projects" replace/>}/></Routes></AuthProvider>}
