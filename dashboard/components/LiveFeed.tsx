import React from "react";

type LiveEvent = {
  id: string;
  createdAt: string;
  eventType: string;
  message: string;
};

type LiveFeedProps = {
  events: LiveEvent[];
};

export default function LiveFeed({ events }: LiveFeedProps) {
  return (
    <section className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-text">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green" />
          </span>
          <span>LIVE</span>
        </div>
      </div>
      <div className="max-h-96 space-y-2 overflow-y-auto text-sm">
        {events.length === 0 && (
          <div className="text-muted">No events yet. Waiting for Skill Forge…</div>
        )}
        {events.map((event) => (
          <div
            key={event.id}
            className="flex items-start gap-2 rounded border border-border/60 bg-bg/60 p-2"
          >
            <span className="text-xs text-muted">
              {new Date(event.createdAt).toLocaleTimeString()}
            </span>
            <div className="flex-1">
              <div className="text-xs uppercase tracking-wide text-muted">
                {event.eventType}
              </div>
              <div className="text-sm text-text">{event.message}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

