//..

import { Link, useParams } from 'react-router-dom'; //routing?
import { api } from '../api.js'; //fetch the layer
import ActivityLog from '../components/ActivityLog.jsx'; //event feed
import BidForm from '../components/BidForm.jsx'; //submit the form
import StatusBadge from '../components/StatusBadge.jsx'; //status
import Timeline from '../components/Timeline.jsx'; //visual bar
import { TRIGGER_LABEL, clock, countdown, dateOnly, dateTime, money, timeWithSeconds } from '../format.js'; //all the formatters
import { useNow, usePolling } from '../hooks.js'; //custom hooks.


function BidCells({ q }) { //reusable cells!
  return (
    <>
      <td className="num">{money(q.freightCharges)}</td> {/* freight cost */}
      <td className="num">{money(q.originCharges)}</td> {/* origin cost */}
      <td className="num">{money(q.destinationCharges)}</td> {/* dest cost */}
      <td className="num strong">{money(q.totalAmount)}</td> {/* grand total */}
      <td className="num">{q.transitTimeDays} d</td> {/* days count */}
      <td>{dateOnly(q.quoteValidUntil)}</td> {/* validity date */}
      <td className="small muted" title={timeWithSeconds(q.createdAt)}>{clock(q.createdAt)}</td> {/* submitted when */}
    </>
  );
}


export default function AuctionDetail() {
  const { id } = useParams(); //grab id.
  const { data, err, reload } = usePolling(() => api.getRfq(id), 2000); // poll every 2s
  const now = useNow(); //tick-tock tick-tockk

  if (err && !data) { //if something broke,
    return (
      <div className="alert alert-error">
        {err.status === 404 ? 'RFQ not found.' : err.message} <Link to="/">Back</Link>
      </div>
    );
  }
  if (!data) return <p className="muted">Loading…</p>; //not ready yet?

  const { rfq, rankings, bids, activity } = data; //destructure all
  const closeMs = new Date(rfq.currentCloseAt).getTime(); //close the timestamp
  const startMs = new Date(rfq.bidStartAt).getTime(); //start the timestamp!

  return (
    <>
      <Link to="/" className="muted small">← All auctions</Link> {/* go back */}
      <div className="detail-head">
        <div>
          <h1>{rfq.name}</h1> {/* auction title */}
          <div className="muted">{rfq.referenceId} · Pickup {dateOnly(rfq.pickupDate)}</div> {/* meta info */}
        </div>
        <div className="head-right">
          <StatusBadge status={rfq.status} /> {/* status pill */}
          <div className="big-clock">
            {rfq.status === 'ACTIVE' && <>Closes in <b>{countdown(closeMs - now)}</b></>} {/* ticking down */}
            {rfq.status === 'UPCOMING' && <>Starts in <b>{countdown(startMs - now)}</b></>} {/* not yet */}
            {(rfq.status === 'CLOSED' || rfq.status === 'FORCE_CLOSED') && <>Closed {dateTime(rfq.currentCloseAt)}</>} {/* all done */}
          </div>
        </div>
      </div>

      <section className="card">
        <div className="stats">
          <div><span className="label">Bid start</span>{dateTime(rfq.bidStartAt)}</div> {/* when open */}
          <div><span className="label">Original close</span>{dateTime(rfq.bidCloseAt)}</div> {/* planned end */}
          <div>
            <span className="label">Current close</span>
            <b>{dateTime(rfq.currentCloseAt)}</b> {/* maybe shifted */}
            {rfq.extensionCount > 0 && <span className="tag tag-ext">+{rfq.extensionCount} ext</span>} {/* extended badge */}
          </div>
          <div><span className="label">Forced close</span>{dateTime(rfq.forcedCloseAt)}</div> {/* hard stop */}
          <div><span className="label">Trigger window (X)</span>{rfq.config.triggerWindowMinutes} min</div> {/* window size */}
          <div><span className="label">Extension (Y)</span>{rfq.config.extensionMinutes} min</div> {/* extra time */}
          <div className="span-2">
            <span className="label">Extension trigger</span>
            {TRIGGER_LABEL[rfq.config.triggerType].replace('X', rfq.config.triggerWindowMinutes)} {/* human label */}
          </div>
        </div>
        <Timeline rfq={rfq} now={now} /> {/* visual timeline */}
      </section>

      <div className="detail-grid">
        <div className="detail-main">
          <section className="card table-wrap">
            <h2>Supplier ranking</h2>
            {rankings.length === 0 ? <p className="muted">No bids yet.</p> : ( // empty check
              <table className="table">
                <thead>
                  <tr>
                    <th>Rank</th><th>Carrier</th>
                    <th className="num">Freight</th>
                    <th className="num">Origin</th>
                    <th className="num">Dest.</th>
                    <th className="num">Total</th>
                    <th className="num">Transit</th>
                    <th>Valid until</th>
                    <th>Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.map((r) => (
                    <tr key={r.id} className={r.rank === 1 ? 'row-l1' : ''}> {/* highlight winner */}
                      <td><span className={`rank rank-${Math.min(r.rank, 4)}`}>{r.label}</span></td> {/* rank badge */}
                      <td className="strong">{r.carrierName}</td> {/* carrier name */}
                      <BidCells q={r} />
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card table-wrap">
            <h2>All bids <span className="muted small">sorted by price · {bids.length} total</span></h2> {/* bid count */}
            {bids.length === 0 ? <p className="muted">No bids yet.</p> : ( // empty check
              <table className="table">
                <thead>
                  <tr>
                    <th>Carrier</th>
                    <th className="num">Freight</th>
                    <th className="num">Origin</th>
                    <th className="num">Dest.</th>
                    <th className="num">Total</th>
                    <th className="num">Transit</th>
                    <th>Valid until</th>
                    <th>Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {bids.map((b) => (
                    <tr key={b.id} className={b.isCurrent ? '' : 'row-old'}> {/* fade old */}
                      <td>
                        {b.carrierName}
                        <span className="sub">{b.isCurrent ? 'current quote' : 'superseded'}</span> {/* quote status */}
                      </td>
                      <BidCells q={b} />
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        <aside className="detail-side">
          {rfq.status === 'ACTIVE' //only if live!!!!
            ? <BidForm rfqId={rfq.id} rankings={rankings} onPlaced={reload} />
            : (
              <div className="card">
                <h2>Submit quote</h2>
                <p className="muted">
                  {rfq.status === 'UPCOMING'
                    ? `Bidding opens ${dateTime(rfq.bidStartAt)}.` //not yet open/
                    : 'Bidding is closed for this auction.'} {/* too late */}
                </p>
                {rankings[0] && rfq.status !== 'UPCOMING' && ( //show thee winner
                  <p>Winning quote: <b>{money(rankings[0].totalAmount)}</b> by <b>{rankings[0].carrierName}</b></p>
                )}
              </div>
            )}
          <ActivityLog activity={activity} /> {/* event history */}
        </aside>
      </div>
    </>
  );
}


