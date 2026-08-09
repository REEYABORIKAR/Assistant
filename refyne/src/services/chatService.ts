import type { Chat, ChatMessage } from '../types/models';
const read=<T,>(key:string,fallback:T):T=>JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback)); const write=(key:string,value:unknown)=>localStorage.setItem(key,JSON.stringify(value)); const now=()=>new Date().toISOString();
export const chatService={
  async list(projectId:string){return read<Chat[]>('refyne.chats',[]).filter(c=>c.project_id===projectId).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));},
  async create(projectId:string,userId:string){const date=now();const chat:Chat={id:crypto.randomUUID(),project_id:projectId,user_id:userId,title:'New conversation',created_at:date,updated_at:date};write('refyne.chats',[chat,...read<Chat[]>('refyne.chats',[])]);await this.message(chat.id,'assistant',"Hello. I'm Supervisor AI. Upload a requirement document or tell me what you would like to analyze.");return chat;},
  async messages(chatId:string){return read<ChatMessage[]>('refyne.messages',[]).filter(m=>m.chat_id===chatId).sort((a,b)=>a.created_at.localeCompare(b.created_at));},
  async message(chatId:string,role:'user'|'assistant',content:string){const message:ChatMessage={id:crypto.randomUUID(),chat_id:chatId,role,content,created_at:now()};write('refyne.messages',[...read<ChatMessage[]>('refyne.messages',[]),message]);write('refyne.chats',read<Chat[]>('refyne.chats',[]).map(c=>c.id===chatId?{...c,updated_at:message.created_at,...(role==='user'?{title:content.slice(0,64)}:{})}:c));return message;},
};
