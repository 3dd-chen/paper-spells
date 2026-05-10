import { CheckCircle2 } from 'lucide-react';

/**
 * Shown after the artwork has been successfully submitted to the API.
 */
export function SuccessScreen() {
  return (
    <div className="flex flex-col items-center justify-center space-y-4 py-12">
      <div className="w-16 h-16 bg-green-100 text-green-500 rounded-full flex items-center justify-center">
        <CheckCircle2 size={32} />
      </div>
      <p className="font-medium text-lg">Artwork Submitted!</p>
      <p className="text-sm text-slate-500">Head to the Gallery to see it come alive.</p>
    </div>
  );
}
