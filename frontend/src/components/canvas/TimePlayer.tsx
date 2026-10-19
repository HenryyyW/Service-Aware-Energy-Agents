import { useRef } from 'react';
import { clsx } from 'clsx';
import { Play, Pause, SkipBack, SkipForward, RotateCcw, FastForward } from 'lucide-react';
import { useTimePlayer } from '../../hooks/useSimulation';
import { useTimePlayerAutoAdvance, useTimePlayerKeyboard } from '../../hooks/useTimePlayer';
import { Slider } from '../ui/Slider';
import { Button } from '../ui/Button';
import { Tooltip } from '../ui/Modal';

export function TimePlayer() {
  const {
    playing,
    currentTimestep,
    minTimestep,
    maxTimestep,
    speed,
    pause,
    togglePlay,
    stepForward,
    stepBackward,
    setSpeed,
    reset,
    setCurrentTimestep,
  } = useTimePlayer();

  // Enable auto-advance and keyboard shortcuts
  useTimePlayerAutoAdvance();
  useTimePlayerKeyboard();

  const sliderRef = useRef<HTMLInputElement>(null);

  const formatTime = (timestep: number) => {
    const hours = Math.floor(timestep * 0.25); // 15-min timesteps
    const minutes = (timestep % 4) * 15;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
  };

  const formatTimestep = (timestep: number) => {
    return `Step ${timestep}`;
  };

  const handleSliderChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentTimestep(Number(event.target.value));
  };

  const handleSliderMouseDown = () => {
    // Pause when user starts dragging
    if (playing) pause();
  };

  const handleSliderMouseUp = () => {
    // Could resume if needed
  };

  const progress = maxTimestep > minTimestep
    ? ((currentTimestep - minTimestep) / (maxTimestep - minTimestep)) * 100
    : 0;

  return (
    <div className="time-player">
      <div className="max-w-[1400px] mx-auto px-4 py-3">
        {/* Main slider */}
        <div className="relative mb-3">
          <div
            className="absolute top-1/2 left-0 right-0 h-1 bg-border rounded-full -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          >
            <div
              className="h-full bg-sun rounded-full transition-all duration-fast"
              style={{ width: `${progress}%` }}
            />
          </div>
          <Slider
            ref={sliderRef}
            min={minTimestep}
            max={maxTimestep}
            step={1}
            value={currentTimestep}
            onChange={handleSliderChange}
            onMouseDown={handleSliderMouseDown}
            onMouseUp={handleSliderMouseUp}
            onTouchStart={handleSliderMouseDown}
            onTouchEnd={handleSliderMouseUp}
            aria-label="Simulation timestep"
            aria-valuemin={minTimestep}
            aria-valuemax={maxTimestep}
            aria-valuenow={currentTimestep}
            aria-valuetext={`${formatTime(currentTimestep)} (${formatTimestep(currentTimestep)})`}
          />
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-2">
          {/* Time display */}
          <div className="flex items-center gap-4 text-body-sm text-text-muted min-w-[200px]">
            <span className="font-mono text-data text-sun tabular-nums w-[80px] text-right">
              {formatTime(currentTimestep)}
            </span>
            <span className="text-text-muted/50 hidden sm:block">
              {formatTimestep(currentTimestep)}
            </span>
            <span className="text-text-muted/50">
              / {formatTime(maxTimestep)}
            </span>
          </div>

          {/* Playback controls */}
          <div className="flex items-center gap-1">
            <Tooltip content="Reset (Home)" position="top">
              <Button
                variant="ghost"
                size="icon"
                onClick={reset}
                aria-label="Reset to start"
              >
                <RotateCcw className="w-5 h-5" />
              </Button>
            </Tooltip>

            <Tooltip content="Step Back (←)" position="top">
              <Button
                variant="ghost"
                size="icon"
                onClick={stepBackward}
                disabled={currentTimestep <= minTimestep}
                aria-label="Step backward"
              >
                <SkipBack className="w-5 h-5" />
              </Button>
            </Tooltip>

            <Tooltip content={playing ? 'Pause (Space)' : 'Play (Space)'} position="top">
              <Button
                variant="primary"
                size="lg"
                onClick={togglePlay}
                aria-label={playing ? 'Pause simulation' : 'Play simulation'}
                className="w-12 h-12 p-0"
                style={{ padding: 0 }}
              >
                {playing ? (
                  <Pause className="w-6 h-6" />
                ) : (
                  <Play className="w-6 h-6 ml-1" />
                )}
              </Button>
            </Tooltip>

            <Tooltip content="Step Forward (→)" position="top">
              <Button
                variant="ghost"
                size="icon"
                onClick={stepForward}
                disabled={currentTimestep >= maxTimestep}
                aria-label="Step forward"
              >
                <SkipForward className="w-5 h-5" />
              </Button>
            </Tooltip>

            <Tooltip content="Speed: {timePlayer.speed}x (↑/↓ to change)" position="top">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSpeed(
                  speed === 1 ? 2 : speed === 2 ? 4 : 1
                )}
                aria-label={`Playback speed: ${speed}x`}
              >
                <FastForward className="w-5 h-5" />
                <span className="font-mono text-data ml-1">{speed}x</span>
              </Button>
            </Tooltip>
          </div>

          {/* Status indicators */}
          <div className="flex items-center gap-4 text-body-sm ml-4">
            <span className={clsx(
              'flex items-center gap-1.5 font-mono text-data',
              playing ? 'text-energy' : 'text-text-muted'
            )}>
              <span className={clsx(
                'w-2 h-2 rounded-full',
                playing ? 'bg-energy animate-pulse' : 'bg-text-muted'
              )} />
              {playing ? 'LIVE' : 'PAUSED'}
            </span>

            {currentTimestep === maxTimestep && playing && (
              <span className="text-violation font-mono text-data">END REACHED</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}