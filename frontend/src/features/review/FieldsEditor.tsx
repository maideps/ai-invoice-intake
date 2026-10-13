import { Plus, RotateCcw, Save, Trash2, Wand2 } from "lucide-react";
import { forwardRef, type ComponentProps, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { confidenceLevel, HEADER_FIELDS, type ConfidenceLevel, type Draft, type LineDraft } from "./draft";

const LEVEL_STYLES: Record<ConfidenceLevel, { label: string; badge: string; field: string }> = {
  high: { label: "High", badge: "text-[var(--status-good)]", field: "" },
  medium: { label: "Medium", badge: "text-muted", field: "" },
  low: {
    label: "Low",
    badge: "bg-[var(--status-review-soft)] text-[var(--status-review)]",
    field: "border-[var(--status-review)]/60 bg-[var(--status-review-soft)]/40",
  },
};

interface Props {
  draft: Draft;
  onChange: (draft: Draft) => void;
  confidence: Record<string, number> | null;
  editable: boolean;
  dirty: boolean;
  saving: boolean;
  errors: Record<string, string[]>;
  onSave: () => void;
  onReset: () => void;
  /** A field gained focus: "total", or "line_items.0.amount" for a line item cell. */
  onFocusField: (key: string) => void;
  onNextLowConfidence: () => void;
}

/** The extracted values, editable while the invoice waits for review. */
export function FieldsEditor(props: Props) {
  const { draft, onChange, confidence, editable, errors } = props;
  const lowCount = confidence
    ? HEADER_FIELDS.filter((def) => confidenceLevel(confidence[def.name] ?? 1) === "low").length
    : 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    props.onSave();
  }

  function setLine(index: number, change: Partial<LineDraft>) {
    onChange({
      ...draft,
      line_items: draft.line_items.map((line, i) => (i === index ? { ...line, ...change } : line)),
    });
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-border bg-surface" aria-label="Invoice fields">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
        <h2 className="flex-1 font-medium">Extracted fields</h2>
        {editable && lowCount > 0 && (
          <Button type="button" size="sm" variant="ghost" onClick={props.onNextLowConfidence}>
            <Wand2 /> Next low-confidence field ({lowCount})
          </Button>
        )}
      </div>

      <div className="grid gap-x-4 gap-y-3 p-5 sm:grid-cols-2">
        {HEADER_FIELDS.map((def) => {
          const score = confidence?.[def.name];
          const level = score === undefined ? null : confidenceLevel(score);
          const fieldErrors = errors[def.name];
          const id = `field-${def.name}`;
          return (
            <div key={def.name} className={cn("space-y-1", def.name === "vendor_name" && "sm:col-span-2")}>
              <div className="flex items-center justify-between gap-2">
                <label htmlFor={id} className="text-xs font-medium text-muted">
                  {def.label}
                </label>
                {level && score !== undefined && (
                  <span
                    className={cn("tabular rounded px-1.5 py-0.5 text-[11px]", LEVEL_STYLES[level].badge)}
                    title="How sure the AI is that this value is right (its own estimate)"
                  >
                    {LEVEL_STYLES[level].label} · {score.toFixed(2)}
                  </span>
                )}
              </div>
              <FieldInput
                id={id}
                data-field={def.name}
                data-confidence={level ?? undefined}
                type={def.input === "date" ? "date" : "text"}
                inputMode={def.input === "money" ? "decimal" : undefined}
                maxLength={def.input === "currency" ? 3 : undefined}
                placeholder={def.input === "money" ? "0.00" : def.input === "currency" ? "EUR" : undefined}
                value={draft[def.name]}
                readOnly={!editable}
                aria-invalid={fieldErrors ? true : undefined}
                aria-describedby={fieldErrors ? `${id}-error` : undefined}
                className={cn(
                  level && LEVEL_STYLES[level].field,
                  def.input === "money" && "tabular text-right",
                  def.input === "currency" && "uppercase",
                )}
                onChange={(event) => onChange({ ...draft, [def.name]: event.target.value })}
                onFocus={() => props.onFocusField(def.name)}
              />
              {fieldErrors && (
                <p id={`${id}-error`} className="text-xs text-[var(--status-bad)]">
                  {fieldErrors.join(" · ")}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="border-t border-border px-5 py-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium">Line items</h3>
          {confidence?.line_items !== undefined && (
            <span className="tabular text-[11px] text-muted">
              {LEVEL_STYLES[confidenceLevel(confidence.line_items)].label} confidence · {confidence.line_items.toFixed(2)}
            </span>
          )}
        </div>
        {draft.line_items.length === 0 ? (
          <p className="text-sm text-muted">No line items.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="pb-1 font-medium">Description</th>
                <th className="w-16 pb-1 text-right font-medium">Qty</th>
                <th className="w-24 pb-1 text-right font-medium">Unit price</th>
                <th className="w-24 pb-1 text-right font-medium">Amount</th>
                {editable && <th className="w-8" />}
              </tr>
            </thead>
            <tbody>
              {draft.line_items.map((line, index) => (
                <tr key={index}>
                  <td className="py-1 pr-2">
                    <FieldInput
                      aria-label={`Line ${index + 1} description`}
                      value={line.description}
                      readOnly={!editable}
                      onChange={(event) => setLine(index, { description: event.target.value })}
                      onFocus={() => props.onFocusField(`line_items.${index}.description`)}
                    />
                  </td>
                  {(["quantity", "unit_price", "amount"] as const).map((key) => (
                    <td key={key} className="py-1 pl-1">
                      <FieldInput
                        aria-label={`Line ${index + 1} ${key.replace("_", " ")}`}
                        value={line[key]}
                        readOnly={!editable}
                        inputMode="decimal"
                        className="tabular text-right"
                        onChange={(event) => setLine(index, { [key]: event.target.value })}
                        onFocus={() => props.onFocusField(`line_items.${index}.${key}`)}
                      />
                    </td>
                  ))}
                  {editable && (
                    <td className="py-1 pl-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove line ${index + 1}`}
                        onClick={() => onChange({ ...draft, line_items: draft.line_items.filter((_, i) => i !== index) })}
                      >
                        <Trash2 />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {errors.line_items && <p className="mt-1 text-xs text-[var(--status-bad)]">{errors.line_items.join(" · ")}</p>}
        {editable && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() =>
              onChange({
                ...draft,
                line_items: [...draft.line_items, { description: "", quantity: "1", unit_price: "", amount: "" }],
              })
            }
          >
            <Plus /> Add line
          </Button>
        )}
      </div>

      {errors.general && (
        <p role="alert" className="px-5 pb-3 text-sm text-[var(--status-bad)]">
          {errors.general.join(" · ")}
        </p>
      )}

      {editable && (
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <span className="mr-auto text-xs text-muted">{props.dirty ? "Unsaved changes" : "All changes saved"}</span>
          <Button type="button" size="sm" variant="ghost" onClick={props.onReset} disabled={!props.dirty || props.saving}>
            <RotateCcw /> Reset
          </Button>
          <Button type="submit" size="sm" disabled={!props.dirty || props.saving}>
            <Save /> {props.saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      )}
    </form>
  );
}

const FieldInput = forwardRef<HTMLInputElement, ComponentProps<"input">>(function FieldInput(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm outline-none transition-colors",
        "focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-ring",
        "read-only:border-transparent read-only:bg-surface-muted",
        "aria-[invalid=true]:border-[var(--status-bad)]",
        className,
      )}
      {...props}
    />
  );
});
