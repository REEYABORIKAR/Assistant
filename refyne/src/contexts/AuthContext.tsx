import { createContext, useContext } from 'react';

// Temporary local workspace identity while authentication is intentionally removed.
type LocalUser = { id: string; email?: string; user_metadata: { full_name: string } };
type LocalState = { user: LocalUser; loading: false; setupError: null };
const localUser: LocalUser = { id: 'local-workspace', user_metadata: { full_name: 'Business Analyst' } };
const LocalContext = createContext<LocalState>({ user: localUser, loading: false, setupError: null });
export function AuthProvider({ children }: { children: React.ReactNode }) { return <LocalContext.Provider value={{ user: localUser, loading: false, setupError: null }}>{children}</LocalContext.Provider>; }
export const useAuth = () => useContext(LocalContext);
