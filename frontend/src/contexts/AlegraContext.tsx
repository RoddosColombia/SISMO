import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useAuth } from "./AuthContext";

interface Account {
  id: string | number;
  name: string;
  code?: string;
  type?: string;
  depth?: number;
  hasChildren?: boolean;
  subAccounts?: Account[];
}

interface DefaultAccount {
  account_id: string | number;
  account_code?: string;
  account_name?: string;
  operation_type?: string;
}

type ConnectionStatus = "connected" | "demo" | "error" | "token_invalid" | "unknown";

interface AlegraContextType {
  accounts: Account[];
  flatAccounts: Account[];
  loadingAccounts: boolean;
  contacts: unknown[];
  bankAccounts: unknown[];
  defaultAccounts: Record<string, DefaultAccount>;
  connectionStatus: ConnectionStatus;
  isDemoMode: boolean;
  searchAccounts: (query: string, filterType?: string | null, allowedCodes?: string[] | null) => Account[];
  getDefaultAccount: (operationType: string) => { id: string | number; code?: string; name?: string } | null;
  checkConnection: () => Promise<void>;
  loadAccounts: () => Promise<void>;
  loadContacts: () => Promise<void>;
  setIsDemoMode: (v: boolean) => void;
  setConnectionStatus: (v: ConnectionStatus) => void;
}

const AlegraContext = createContext<AlegraContextType | null>(null);

export function AlegraProvider({ children }: { children: React.ReactNode }) {
  const { api, token } = useAuth();
  const [accounts, setAccounts]               = useState<Account[]>([]);
  const [flatAccounts, setFlatAccounts]       = useState<Account[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("unknown");
  const [isDemoMode, setIsDemoMode]           = useState(true);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [contacts, setContacts]               = useState<unknown[]>([]);
  const [bankAccounts, setBankAccounts]       = useState<unknown[]>([]);
  const [defaultAccounts, setDefaultAccounts] = useState<Record<string, DefaultAccount>>({});

  const flattenAccounts = useCallback((accs: Account[], depth = 0): Account[] => {
    const result: Account[] = [];
    for (const acc of accs) {
      result.push({ ...acc, depth, hasChildren: (acc.subAccounts?.length ?? 0) > 0 });
      if (acc.subAccounts?.length) result.push(...flattenAccounts(acc.subAccounts, depth + 1));
    }
    return result;
  }, []);

  const loadAccounts = useCallback(async () => {
    if (!token) return;
    setLoadingAccounts(true);
    try {
      const resp = await api.get("/alegra/accounts");
      setAccounts(resp.data);
      setFlatAccounts(flattenAccounts(resp.data));
    } catch { /* silent */ } finally { setLoadingAccounts(false); }
  }, [token, api, flattenAccounts]);

  const loadContacts = useCallback(async () => {
    if (!token) return;
    try { const resp = await api.get("/alegra/contacts"); setContacts(resp.data); } catch { /* silent */ }
  }, [token, api]);

  const loadBankAccounts = useCallback(async () => {
    if (!token) return;
    try { const resp = await api.get("/alegra/bank-accounts"); setBankAccounts(resp.data); } catch { /* silent */ }
  }, [token, api]);

  const loadDefaultAccounts = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.get("/settings/default-accounts");
      const map: Record<string, DefaultAccount> = {};
      for (const item of resp.data) map[item.operation_type] = item;
      setDefaultAccounts(map);
    } catch { /* silent */ }
  }, [token, api]);

  const checkConnection = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.post("/alegra/test-connection");
      const status = resp.data.status as ConnectionStatus;
      setConnectionStatus(status);
      setIsDemoMode(status === "demo");
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { detail?: string }; status?: number } };
      const detail = anyErr.response?.data?.detail ?? "";
      setConnectionStatus(detail.includes("token") || detail.includes("inválid") || anyErr.response?.status === 400 ? "token_invalid" : "error");
    }
  }, [token, api]);

  const searchAccounts = useCallback((query: string, filterType: string | null = null, allowedCodes: string[] | null = null): Account[] => {
    let filtered = [...flatAccounts];
    if (filterType && filterType !== "all") {
      const typeMap: Record<string, string[]> = { income: ["income"], expense: ["expense", "cost"], asset: ["asset"], liability: ["liability"], equity: ["equity"] };
      const types = typeMap[filterType] ?? [];
      if (types.length) filtered = filtered.filter(acc => {
        if (acc.code) {
          const codePrefixMap: Record<string, string[]> = { income: ["4"], expense: ["5","6","7"], asset: ["1"], liability: ["2"], equity: ["3"] };
          return types.includes(acc.type ?? "") || (codePrefixMap[filterType] ?? []).some(p => acc.code!.startsWith(p));
        }
        return types.includes(acc.type ?? "");
      });
    }
    if (allowedCodes?.length && filtered.some(a => a.code)) {
      filtered = filtered.filter(acc => !acc.code || allowedCodes.some(c => acc.code!.startsWith(c)));
    }
    if (query) {
      const q = query.toLowerCase();
      filtered = filtered.filter(acc => acc.code?.includes(q) || acc.name?.toLowerCase().includes(q));
    }
    return filtered;
  }, [flatAccounts]);

  const getDefaultAccount = useCallback((operationType: string) => {
    const da = defaultAccounts[operationType];
    if (!da) return null;
    return { id: da.account_id, code: da.account_code, name: da.account_name };
  }, [defaultAccounts]);

  useEffect(() => {
    if (token) { checkConnection(); loadAccounts(); loadContacts(); loadBankAccounts(); loadDefaultAccounts(); }
  }, [token]); // eslint-disable-line

  return (
    <AlegraContext.Provider value={{ accounts, flatAccounts, loadingAccounts, contacts, bankAccounts, defaultAccounts, connectionStatus, isDemoMode, searchAccounts, getDefaultAccount, checkConnection, loadAccounts, loadContacts, setIsDemoMode, setConnectionStatus }}>
      {children}
    </AlegraContext.Provider>
  );
}

export function useAlegra(): AlegraContextType {
  const ctx = useContext(AlegraContext);
  if (!ctx) throw new Error("useAlegra must be used within AlegraProvider");
  return ctx;
}
