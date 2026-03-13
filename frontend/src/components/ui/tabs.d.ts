import * as React from "react";

export declare const Tabs: React.FC<{
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  children?: React.ReactNode;
}>;

export declare const TabsList: React.ForwardRefExoticComponent<
  React.HTMLAttributes<HTMLDivElement> & React.RefAttributes<HTMLDivElement>
>;

export declare const TabsTrigger: React.ForwardRefExoticComponent<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    value: string;
  } & React.RefAttributes<HTMLButtonElement>
>;

export declare const TabsContent: React.ForwardRefExoticComponent<
  React.HTMLAttributes<HTMLDivElement> & {
    value: string;
  } & React.RefAttributes<HTMLDivElement>
>;

