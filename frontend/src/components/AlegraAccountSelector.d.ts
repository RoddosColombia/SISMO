import * as React from "react";

interface AlegraAccountSelectorProps {
  label: any;
  value: any;
  onChange: any;
  filterType?: string;
  required?: boolean;
  placeholder?: string;
  helpText?: any;
  allowedCodes?: any;
}

declare const AlegraAccountSelector: React.FC<AlegraAccountSelectorProps>;
export default AlegraAccountSelector;
