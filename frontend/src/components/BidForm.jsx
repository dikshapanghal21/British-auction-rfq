// 

import { useState } from 'react'; //hooks gang
import { api } from '../api.js'; //fetch stuff!
import { dateTime, money, toLocalDateInput } from '../format.js'; //pretty print

function emptyForm() { //clean slate..
  return {
    carrierName: '',
    freightCharges: '',
    originCharges: '',
    destinationCharges: '',
    transitTimeDays: '',
    quoteValidUntil: toLocalDateInput(Date.now() + 30 * 24 * 60 * 60 * 1000), //30 days ahead..
  };
}

export default function BidForm({ rfqId, rankings, onPlaced }) {
  const [form, setForm] = useState(emptyForm); //form state.
  const [errs, setErrs] = useState({}); //track errors..
  const [result, setResult] = useState(null); //bid outcome
  const [saving, setSaving] = useState(false); //loading guard.

  const setField = (key) => (ev) => setForm((f) => ({ ...f, [key]: ev.target.value })); //field updater/

  const totalAmt = ['freightCharges', 'originCharges', 'destinationCharges']
    .reduce((sum, k) => sum + (Number(form[k]) || 0), 0); //sum it up'

  const myEntry = rankings.find(
    (r) => r.carrierName.toLowerCase() === form.carrierName.trim().toLowerCase() //find myself!!
  );

  async function onSubmit(ev) {
    ev.preventDefault(); //no page refresh.
    setSaving(true); //lock it?
    setErrs({}); //fresh start
    setResult(null); //clear old one
    try {
      const res = await api.submitBid(rfqId, { //fire away
        ...form,
        freightCharges: form.freightCharges === '' ? '' : Number(form.freightCharges), //coerce number?
        originCharges: form.originCharges === '' ? '' : Number(form.originCharges),
        destinationCharges: form.destinationCharges === '' ? '' : Number(form.destinationCharges), 
        transitTimeDays: form.transitTimeDays === '' ? '' : Number(form.transitTimeDays), 
      });
      setResult({ ok: true, ...res }); //success!
      setForm((f) => ({
        ...emptyForm(),
        carrierName: f.carrierName, //keep carrier
        transitTimeDays: f.transitTimeDays, //keep transit
        quoteValidUntil: f.quoteValidUntil, //keep date
      }));
      onPlaced(); //notify parent
    } catch (e) {
      setErrs(e.details || {}); //show field errors
      setResult({ ok: false, message: e.message }); //show message.
    } finally {
      setSaving(false); //unlock form
    }
  }

  function inputRow(key, label, props = {}) { //reusable field.
    return (
      <label className={`field ${errs[key] ? 'has-error' : ''}`}> {/* highlight error */}
        <span className="label">{label}</span>
        <input value={form[key]} onChange={setField(key)} {...props} /> {/* controlled input */}
        {errs[key] && <span className="error">{errs[key]}</span>} {/* inline error */}
      </label>
    );
  }

  return (
    <form className="card bid-form" onSubmit={onSubmit} noValidate> {/* no browser validation */}
      <h2>Submit quote</h2>

      {inputRow('carrierName', 'Carrier name *', { list: 'carriers', placeholder: 'e.g. Blue Dart Cargo', autoComplete: 'off' })}
      <datalist id="carriers"> {/* autocomplete list */}
        {rankings.map((r) => <option key={r.supplierId} value={r.carrierName} />)}
      </datalist>

      {myEntry && ( //already bidded!!
        <p className="hint">
          Current quote: <b>{money(myEntry.totalAmount)}</b> ({myEntry.label}). New total must be lower.
        </p>
      )}

      <div className="grid-3 tight"> {/* three columns */}
        {inputRow('freightCharges', 'Freight (₹) *', { type: 'number', min: 0, step: '0.01' })}
        {inputRow('originCharges', 'Origin (₹) *', { type: 'number', min: 0, step: '0.01' })}
        {inputRow('destinationCharges', 'Destination (₹) *', { type: 'number', min: 0, step: '0.01' })}
      </div>
      <div className="grid-2 tight"> {/* two columns */}
        {inputRow('transitTimeDays', 'Transit time (days) *', { type: 'number', min: 1, step: 1 })}
        {inputRow('quoteValidUntil', 'Quote valid until *', { type: 'date' })}
      </div>

      <div className="total-row"> {/* show total */}
        <span>Total quote</span>
        <b>{money(totalAmt)}</b> {/* formatted nicely */}
      </div>

      <button className="btn btn-primary btn-block" disabled={saving}> {/* disable while saving */}
        {saving ? 'Submitting…' : 'Submit bid'} {/* dynamic label */}
      </button>

      {result && ( // show the result.
        result.ok ? (
          <div className="alert alert-ok"> {/* happy path */}
            Bid placed. You are <b>L{result.rank}</b>.
            {result.extension && ( // time extended
              <div className="small">
                Auction extended to <b>{dateTime(result.extension.newCloseAt)}</b>
                {result.extension.capped && ' (capped at forced close)'} — {result.extension.reason}
              </div>
            )}
            {result.note && <div className="small">{result.note}</div>} {/* extra info */}
          </div>
        ) : (
          <div className="alert alert-error">{result.message}</div> //sad path!
        )
      )}
    </form>
  );
}


