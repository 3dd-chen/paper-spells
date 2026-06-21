import { CheckCircle2 } from 'lucide-react';

/**
 * Shown after the artwork has been successfully submitted to the API.
 */
export function SuccessScreen() {
  return (
    <div className="flex flex-col items-center justify-center space-y-4 py-10">
      <div className="w-20 h-20 bg-sun text-ink rounded-full border-2 border-ink shadow-pop flex items-center justify-center animate-bob">
        <CheckCircle2 size={38} strokeWidth={2.25} />
      </div>
      <p className="font-display font-black text-2xl text-ink">Artwork Submitted!</p>
      <p className="text-sm text-inksoft">Head to the Gallery to see it come alive.</p>
    </div>
  );
}
