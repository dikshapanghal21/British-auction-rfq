//..

import { dateTime } from '../format.js'; //date the helper

export default function Timeline({ rfq, now }) {
  const startMs = new Date(rfq.bidStartAt).getTime(); //auction begins...
  const forcedMs = new Date(rfq.forcedCloseAt).getTime(); //hard deadline
  const origCloseMs = new Date(rfq.bidCloseAt).getTime(); //planned close.
  const currCloseMs = new Date(rfq.currentCloseAt).getTime(); //maybe extended?
  const winStartMs = currCloseMs - rfq.config.triggerWindowMinutes * 60_000; //window starts here

  const totalSpan = forcedMs - startMs; //for full duration
  const pct = (t) => `${Math.min(100, Math.max(0, ((t - startMs) / totalSpan) * 100))}%`; 

  const isOpen = rfq.status === 'ACTIVE'; //still goinggg

  return (
    <div className="timeline">
      <div className="track">
        <div className="fill" style={{ width: pct(Math.min(now, currCloseMs)) }} /> {/* elapsed bar */}
        {isOpen && ( //show the window..
          <div className="window"
            style={{ left: pct(winStartMs), width: `calc(${pct(currCloseMs)} - ${pct(winStartMs)})` }}
            title="Trigger window" />
        )}
        <div className="extended"
          style={{ left: pct(origCloseMs), width: `calc(${pct(currCloseMs)} - ${pct(origCloseMs)})` }}
          title="Extensions" /> {/* extension zone */}
        <span className="mark mark-original" style={{ left: pct(origCloseMs) }}
          title={`Original close ${dateTime(rfq.bidCloseAt)}`} /> {/* original marker */}
        <span className="mark mark-current" style={{ left: pct(currCloseMs) }}
          title={`Current close ${dateTime(rfq.currentCloseAt)}`} /> {/* current marker */}
        {isOpen && <span className="mark mark-now" style={{ left: pct(now) }} title="Now" />} {/* you are here */}
      </div>
      <div className="timeline-legend small"> {/* bottom legend */}
        <span><i className="dot dot-fill" />Elapsed</span>
        {isOpen && <span><i className="dot dot-window" />Trigger window (last {rfq.config.triggerWindowMinutes} min)</span>}
        <span><i className="dot dot-original" />Original close</span>
        <span><i className="dot dot-extended" />Extended</span>
        <span><i className="dot dot-current" />Current close</span>
        <span className="push">Forced close ▸</span> {/* no escape */}
      </div>
    </div>
  );
}


