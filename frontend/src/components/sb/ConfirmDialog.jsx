import { useState } from "react";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter } from "@/components/ui/alert-dialog";

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", requireReason, danger, onConfirm }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await onConfirm(reason);
      setReason("");
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid="confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        {requireReason && (
          <textarea className="inp" rows={2} placeholder="Reason (required, saved in audit history)" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="confirm-reason-input" />
        )}
        <AlertDialogFooter>
          <button className="btn-outline" onClick={() => onOpenChange(false)} data-testid="confirm-cancel-btn">Cancel</button>
          <button className={danger ? "btn-primary" : "btn-dark"} disabled={busy || (requireReason && reason.trim().length < 3)} onClick={run} data-testid="confirm-ok-btn">
            {busy ? "Please wait…" : confirmLabel}
          </button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
