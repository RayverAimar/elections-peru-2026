interface Props {
  current: number;
  total: number;
  percent: number;
  topic: string;
  confidence?: string | null;
}

export default function QuizProgress({ current, total, percent, topic, confidence }: Props) {
  return (
    <div>
      {/* Row 1: counter + confidence badge */}
      <div class="flex items-center justify-between">
        <span class="text-sm font-medium text-surface-700">
          <span class="text-white">{current}</span>
          <span class="text-surface-500"> / {total} máx</span>
        </span>
        {confidence && (
          <span class={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            confidence === 'Alta' ? 'bg-green-500/10 text-green-400' :
            confidence === 'Media' ? 'bg-yellow-500/10 text-yellow-400' :
            'bg-surface-300/30 text-surface-500'
          }`}>
            {confidence}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-300/30">
        <div
          class="h-full rounded-full bg-accent transition-all duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Row 2: topic name below bar */}
      <p class="mt-2 text-xs text-surface-500">{topic}</p>
    </div>
  );
}
