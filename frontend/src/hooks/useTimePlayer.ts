import { useRef, useEffect } from 'react';
import { useSimulationStore } from '../store/simulationStore';

export function useTimePlayerAutoAdvance() {
  const { timePlayer, setCurrentTimestep } = useSimulationStore();
  const intervalRef = useRef<number | null>(null);
  const lastFrameRef = useRef<number>(0);

  const fpsMap = { 1: 2, 2: 4, 4: 8 }; // frames per second per speed

  useEffect(() => {
    if (timePlayer.playing && timePlayer.currentTimestep < timePlayer.maxTimestep) {
      const fps = fpsMap[timePlayer.speed];
      const frameDuration = 1000 / fps;

      const animate = (timestamp: number) => {
        if (timestamp - lastFrameRef.current >= frameDuration) {
          lastFrameRef.current = timestamp;
          const nextTimestep = timePlayer.currentTimestep + 1;
          if (nextTimestep <= timePlayer.maxTimestep) {
            setCurrentTimestep(nextTimestep);
          } else {
            // Reached end, stop playing
            useSimulationStore.getState().pause();
          }
        }
        intervalRef.current = requestAnimationFrame(animate);
      };

      intervalRef.current = requestAnimationFrame(animate);
    } else {
      if (intervalRef.current) {
        cancelAnimationFrame(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        cancelAnimationFrame(intervalRef.current);
      }
    };
  }, [timePlayer.playing, timePlayer.speed, timePlayer.currentTimestep, timePlayer.maxTimestep, setCurrentTimestep]);
}

export function useTimePlayerKeyboard() {
  const { timePlayer, play, pause, stepForward, stepBackward, setSpeed, reset, setCurrentTimestep } = useSimulationStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle keys if user is typing in an input
      if (e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement ||
          e.target instanceof HTMLSelectElement ||
          (e.target as HTMLElement).isContentEditable) {
        return;
      }

      switch (e.key) {
        case ' ':
          e.preventDefault();
          if (timePlayer.playing) pause(); else play();
          break;
        case 'ArrowRight':
          e.preventDefault();
          stepForward();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          stepBackward();
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (timePlayer.speed < 4) setSpeed((timePlayer.speed * 2) as 1 | 2 | 4);
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (timePlayer.speed > 1) setSpeed((timePlayer.speed / 2) as 1 | 2 | 4);
          break;
        case 'Home':
          e.preventDefault();
          reset();
          break;
        case 'End':
          e.preventDefault();
          setCurrentTimestep(timePlayer.maxTimestep);
          break;
        case '0':
        case '1':
        case '2':
        case '3':
        case '4':
        case '5':
        case '6':
        case '7':
        case '8':
        case '9':
          // Number keys for quick jump (0-9 -> 0%-90%)
          e.preventDefault();
          const percent = parseInt(e.key) * 10;
          const targetTimestep = Math.round(timePlayer.minTimestep + (timePlayer.maxTimestep - timePlayer.minTimestep) * percent / 100);
          setCurrentTimestep(targetTimestep);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [timePlayer, play, pause, stepForward, stepBackward, setSpeed, reset, setCurrentTimestep]);
}