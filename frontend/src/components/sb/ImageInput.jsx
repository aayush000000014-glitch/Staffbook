import { useRef } from "react";
import { toast } from "sonner";
import { ImagePlus, X } from "lucide-react";
import { readImage } from "@/lib/api";

export function ImageInput({ value, onChange, label = "Upload image", testid = "image-input" }) {
  const ref = useRef();
  const pick = async (e) => {
    try {
      onChange(await readImage(e.target.files?.[0]));
    } catch (err) {
      toast.error(err.message);
    }
    e.target.value = "";
  };
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl border border-dashed border-stone-300 bg-stone-50">
        {value ? <img src={value} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="h-5 w-5 text-stone-400" />}
      </div>
      <input ref={ref} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={pick} data-testid={testid} />
      <button type="button" className="btn-outline btn-sm" onClick={() => ref.current.click()} data-testid={`${testid}-btn`}>{label}</button>
      {value && (
        <button type="button" className="btn-ghost btn-sm" onClick={() => onChange(null)} data-testid={`${testid}-remove`}>
          <X className="h-3.5 w-3.5" /> Remove
        </button>
      )}
    </div>
  );
}
