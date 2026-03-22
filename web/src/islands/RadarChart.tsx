import { useEffect, useRef } from 'preact/hooks';

interface Props {
  labels: string[];
  userValues: number[];
  matchValues: number[];
  matchLabel: string;
}

export default function RadarChart({ labels, userValues, matchValues, matchLabel }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    let chartInstance: any = null;

    import('chart.js').then(({ Chart, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend }) => {
      Chart.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

      if (!canvasRef.current) return;

      chartInstance = new Chart(canvasRef.current, {
        type: 'radar',
        data: {
          labels,
          datasets: [
            {
              label: 'Tu perfil',
              data: userValues,
              borderColor: '#60A5FA',
              backgroundColor: 'rgba(96, 165, 250, 0.1)',
              borderWidth: 2,
              pointBackgroundColor: '#60A5FA',
              pointRadius: 3,
              pointHoverRadius: 5,
            },
            {
              label: matchLabel,
              data: matchValues,
              borderColor: '#E11D48',
              backgroundColor: 'rgba(225, 29, 72, 0.08)',
              borderWidth: 2,
              pointBackgroundColor: '#E11D48',
              pointRadius: 3,
              pointHoverRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          scales: {
            r: {
              beginAtZero: true,
              max: 100,
              ticks: {
                stepSize: 25,
                display: false,
              },
              pointLabels: {
                font: { size: 10, family: 'Inter' },
                color: '#A1A1AA',
              },
              grid: {
                color: 'rgba(255,255,255,0.06)',
              },
              angleLines: {
                color: 'rgba(255,255,255,0.06)',
              },
            },
          },
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                usePointStyle: true,
                padding: 20,
                font: { size: 12, family: 'Inter' },
                color: '#A1A1AA',
              },
            },
            tooltip: {
              backgroundColor: '#18181B',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1,
              titleColor: '#FAFAFA',
              bodyColor: '#A1A1AA',
              callbacks: {
                label: (ctx: any) => `${ctx.dataset.label}: ${ctx.parsed.r.toFixed(1)}%`,
              },
            },
          },
        },
      });
    });

    return () => { chartInstance?.destroy(); };
  }, [labels, userValues, matchValues, matchLabel]);

  const altText = `Gráfico radar comparando tu perfil electoral con ${matchLabel} en ${labels.length} temas.`;
  return <canvas ref={canvasRef} role="img" aria-label={altText} />;
}
