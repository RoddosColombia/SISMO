import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useAuth } from "./AuthContext";

const AlegraContext = createContext(null);

export function AlegraProvider({ children }) {
  const { api, token } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [flatAccounts, setFlatAccounts] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState("unknown"); // connected | demo | error | unknown
  const [isDemoMode, setIsDemoMode] = useState(true);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [defaultAccounts, setDefaultAccounts] = useState({});

  const flattenAccounts = useCallback((accs, depth = 0) => {
    const result = [];
    for (const acc of accs) {
      result.push({ ...acc, depth, hasChildren: acc.subAccounts?.length > 0 });
      if (acc.subAccounts?.length > 0) {
        result.push(...flattenAccounts(acc.subAccounts, depth + 1));
      }
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
    } catch (e) {
      console.error("Error loading accounts:", e);
    } finally {
      setLoadingAccounts(false);
    }
  }, [token, api, flattenAccounts]);

  const loadContacts = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.get("/alegra/contacts");
      setContacts(resp.data);
    } catch (e) {
      console.error("Error loading contacts:", e);
    }
  }, [token, api]);

  const loadBankAccounts = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.get("/alegra/bank-accounts");
      setBankAccounts(resp.data);
    } catch (e) {
      console.error("Error loading bank accounts:", e);
    }
  }, [token, api]);

  const loadDefaultAccounts = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.get("/settings/default-accounts");
      const map = {};
      for (const item of resp.data) {
        map[item.operation_type] = item;
      }
      setDefaultAccounts(map);
    } catch (e) {
      console.error("Error loading default accounts:", e);
    }
  }, [token, api]);

  const checkConnection = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await api.post("/alegra/test-connection");
      const status = resp.data.status;
      setConnectionStatus(status);
      setIsDemoMode(status === "demo");
    } catch {
      setConnectionStatus("error");
    }
  }, [token, api]);

  const searchAccounts = useCallback((query, filterType = null, allowedCodes = null) => {
    let filtered = flatAccounts.filter(acc => acc.subAccounts !== undefined);

    if (filterType && filterType !== "all") {
      const typeMap = {
        income: ["4"],
        expense: ["5", "6", "7"],
        asset: ["1"],
        liability: ["2"],
        equity: ["3"],
      };
      const prefixes = typeMap[filterType] || [];
      if (prefixes.length > 0) {
        filtered = filtered.filter(acc => prefixes.some(p => acc.code?.startsWith(p)));
      }
    }

    if (allowedCodes?.length > 0) {
      filtered = filtered.filter(acc =>
        allowedCodes.some(code => acc.code?.startsWith(code))
      );
    }

    if (query) {
      const q = query.toLowerCase();
      filtered = filtered.filter(acc =>
        acc.code?.includes(q) || acc.name?.toLowerCase().includes(q)
      );
    }

    return filtered;
  }, [flatAccounts]);

  const getDefaultAccount = useCallback((operationType) => {
    if (!defaultAccounts[operationType]) return null;
    const da = defaultAccounts[operationType];
    return { id: da.account_id, code: da.account_code, name: da.account_name };
  }, [defaultAccounts]);

  useEffect(() => {
    if (token) {
      checkConnection();
      loadAccounts();
      loadContacts();
      loadBankAccounts();
      loadDefaultAccounts();
    }
  }, [token]); // eslint-disable-line

  return (
    <AlegraContext.Provider value={{
      accounts, flatAccounts, loadingAccounts,
      contacts, bankAccounts, defaultAccounts,
      connectionStatus, isDemoMode,
      searchAccounts, getDefaultAccount,
      checkConnection, loadAccounts, loadContacts,
      setIsDemoMode, setConnectionStatus,
    }}>
      {children}
    </AlegraContext.Provider>
  );
}

export function useAlegra() {
  return useContext(AlegraContext);
}
