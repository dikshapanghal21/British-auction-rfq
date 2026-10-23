//..

//same import!
import { Link, useNavigate } from 'react-router-dom'; 
import { api } from '../api.js'; 
import StatusBadge from '../components/StatusBadge.jsx'; 
import { countdown, dateTime, money } from '../format.js'; 
import { useNow, usePolling } from '../hooks.js'; 

export default function AuctionList() {
  const { data: listData, err } = usePolling(api.listRfqs, 3000); //poll 3s!
  const now = useNow(); //tick-tock tick-tock
  const navigate = useNavigate(); //go places

  if (err && !listData) return <div className="alert alert-error">Could not load auctions: {err.message}</div>; //sad path
  if (!listData) return <p className="muted">Loading…</p>; //not ready!

  const allRfqs = listData.rfqs; //grab the list

  return (
    <>
      <div className="page-head">
        <h1>British Auctions</h1>
        <span className="muted">{allRfqs.length} RFQs · live</span> {/* live count */}
      </div>

      {allRfqs.length === 0 ? ( 
        <div className="card empty">
          No auctions yet. <Link to="/rfqs/new">Create the first RFQ</Link> or run <code>python -m app.seed</code> in the backend.
        </div>
      ) : (
        <div className="card table-wrap">
          <table className="table table-click">
            <thead>
              <tr>
                <th>RFQ Name / ID</th>
                <th className="num">Current Lowest Bid</th>
                <th>Current Bid Close</th>
                <th>Forced Close</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {allRfqs.map((r) => {
                const msLeft = new Date(r.currentCloseAt).getTime() - now; //time remaining?
                const msToStart = new Date(r.bidStartAt).getTime() - now; //starts when!
                return (
                  <tr key={r.id} onClick={() => navigate(`/rfqs/${r.id}`)}> {/* whole row clicks */}
                    <td>
                      <Link to={`/rfqs/${r.id}`} className="strong" onClick={(e) => e.stopPropagation()}> {/* no double nav */}
                        {r.name}
                      </Link>
                      <div className="muted small">{r.referenceId} · {r.bidCount} bids · {r.supplierCount} suppliers</div> {/* quick stats */}
                    </td>
                    <td className="num">
                      {r.lowestBid ? ( //someone bid?
                        <>
                          <div className="strong">{money(r.lowestBid.amount)}</div> {/* best price */}
                          <div className="muted small">{r.lowestBid.carrierName}</div> {/* who bid */}
                        </>
                      ) : <span className="muted">No bids</span>} {/* crickets */}
                    </td>
                    <td>
                      <div>{dateTime(r.currentCloseAt)}</div>
                      <div className="small">
                        {r.status === 'ACTIVE' && <span className="countdown">closes in {countdown(msLeft)}</span>} {/* ticking down */}
                        {r.status === 'UPCOMING' && <span className="muted">starts in {countdown(msToStart)}</span>} {/* not yet */}
                        {r.extensionCount > 0 && <span className="tag tag-ext">+{r.extensionCount} ext</span>} {/* extended badge */}
                      </div>
                    </td>
                    <td>{dateTime(r.forcedCloseAt)}</td> {/* hard deadline */}
                    <td><StatusBadge status={r.status} /></td> {/* status pill */}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}


