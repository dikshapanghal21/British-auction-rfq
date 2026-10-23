import { dateTime, timeWithSeconds } from '../format.js';
//label lookup table!
const EVENT_LABEL = {
  RFQ_CREATED: 'Created',
  BID_SUBMITTED: 'Bid',
  TIME_EXTENDED: 'Extended',
  AUCTION_CLOSED: 'Closed',
  AUCTION_FORCE_CLOSED: 'Force closed',
}; //..
export default function ActivityLog({ activity }) {
  const newestFirst = [...activity].reverse(); //latest on top!
  return (
    <section className="card"> {/* wrap it nicely */}
      <h2>Activity log</h2>
      <ol className="activity"> {/* ordered list */}
        {newestFirst.map((a) => (
          <li key={a.id} className={`act act-${a.eventType.toLowerCase()}`}> {/* unique key */}
            <span className="act-time">{timeWithSeconds(a.createdAt)}</span> {/* when it happened */}
            <span className="act-type">{EVENT_LABEL[a.eventType]}</span> {/* human readable */}
            <div className="act-body">
              <div>{a.message}</div> {/* the gist */}
              {a.eventType === 'TIME_EXTENDED' && ( // only if extended
                <div className="small">
                  <span className="muted">{dateTime(a.oldCloseAt)} → </span> {/* before change */}
                  <b>{dateTime(a.newCloseAt)}</b> {/* after change */}
                  <div><span className="muted">Reason:</span> {a.reason}</div> {/* why tho */}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
