import * as React from "react";

export declare const Dialog: React.FC<{
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
}>;

export declare const DialogTrigger: React.FC<{
  asChild?: boolean;
  children?: React.ReactNode;
}>;

export declare const DialogContent: React.FC<{
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogHeader: React.FC<{
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogFooter: React.FC<{
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogTitle: React.FC<{
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogDescription: React.FC<{
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogClose: React.FC<{
  asChild?: boolean;
  className?: string;
  children?: React.ReactNode;
}>;

export declare const DialogPortal: React.FC<{
  children?: React.ReactNode;
}>;

export declare const DialogOverlay: React.FC<{
  className?: string;
}>;
