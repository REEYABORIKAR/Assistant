import type { Project, Workspace } from '../types/models';
const key = 'refyne.projects'; const read = <T,>(k: string, fallback: T): T => JSON.parse(localStorage.getItem(k) || JSON.stringify(fallback)); const write = (k:string, value:unknown) => localStorage.setItem(k, JSON.stringify(value)); const now = () => new Date().toISOString();
export const projectService = {
  async list(): Promise<Project[]> { return read<Project[]>(key, []).sort((a,b)=>b.updated_at.localeCompare(a.updated_at)); },
  async get(id: string) { const item = read<Project[]>(key, []).find(p=>p.id===id); if (!item) throw new Error('Project not found.'); return item; },
  async create(userId: string, name: string, description: string) { const date=now(); const project:Project={id:crypto.randomUUID(),user_id:userId,name,description:description||null,created_at:date,updated_at:date}; const all=read<Project[]>(key,[]); write(key,[project,...all]); const workspace:Workspace={id:crypto.randomUUID(),project_id:project.id,name:`${name} Workspace`,created_at:date}; write('refyne.workspaces',[workspace,...read<Workspace[]>('refyne.workspaces',[])]); return project; },
  async update(id:string, values:Pick<Project,'name'|'description'>) { let updated!:Project; write(key,read<Project[]>(key,[]).map(p=>p.id===id?(updated={...p,...values,updated_at:now()}):p)); return updated; },
  async remove(id:string) { write(key,read<Project[]>(key,[]).filter(p=>p.id!==id)); write('refyne.workspaces',read<Workspace[]>('refyne.workspaces',[]).filter(w=>w.project_id!==id)); ['refyne.chats','refyne.documents'].forEach(k=>write(k,(read<{project_id:string}[]>(k,[])).filter(x=>x.project_id!==id))); },
  async duplicate(project:Project,userId:string) { return this.create(userId,`${project.name} (Copy)`,project.description||''); },
  async workspace(projectId:string) { return read<Workspace[]>('refyne.workspaces',[]).find(w=>w.project_id===projectId)||null; },
};
