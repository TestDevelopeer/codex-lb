import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type FreemodelImportDialogProps = {
  open: boolean;
  busy: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onImport: (apiKey: string, label?: string) => Promise<void>;
};

export function FreemodelImportDialog({
  open,
  busy,
  error,
  onOpenChange,
  onImport,
}: FreemodelImportDialogProps) {
  const [apiKey, setApiKey] = useState("");
  const [label, setLabel] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      return;
    }
    const trimmedLabel = label.trim();
    await onImport(trimmedKey, trimmedLabel || undefined);
    onOpenChange(false);
    setApiKey("");
    setLabel("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add FreeModel API key</DialogTitle>
          <DialogDescription>
            Paste a FreeModel API key from your dashboard. Requests for this account will be routed to api.freemodel.dev.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="freemodel-api-key">API key</Label>
            <Input
              id="freemodel-api-key"
              type="password"
              autoComplete="off"
              placeholder="fm-..."
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="freemodel-label">Label (optional)</Label>
            <Input
              id="freemodel-label"
              placeholder="My FreeModel key"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
          </div>

          {error ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-2 py-1 text-xs text-destructive">
              {error}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={busy || !apiKey.trim()}>
              Add key
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
