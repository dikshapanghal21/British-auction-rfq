//..

import { useState } from 'react'; 
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api.js'; 
import { TRIGGER_LABEL, toLocalDateInput, toLocalInput } from '../format.js'; 

const ONE_HOUR_MS = 60 * 60 * 1000; //1 hr
const HALF_HOUR_MS = 30 * 60 * 1000; //half hr
const THREE_DAYS_MS = 3 * 24 * 60 * 60 * 1000; //3 days

function getInitialForm() { //fresh defaults.
  const now = Date.now(); 
  return {
    name: '',
    referenceId: '',
    pickupDate: toLocalDateInput(now + THREE_DAYS_MS), //3 days out
    bidStartAt: toLocalInput(now), //starts now!!
    bidCloseAt: toLocalInput(now + HALF_HOUR_MS), //30 min window
    forcedCloseAt: toLocalInput(now + ONE_HOUR_MS), //hard stop
    triggerWindowMinutes: 10,
    extensionMinutes: 5,
    triggerType: 'BID_RECEIVED',
  };
}

function validateForm(f) { //check everything!!
  const errs = {};
  const startMs = new Date(f.bidStartAt).getTime(); 
  const closeMs = new Date(f.bidCloseAt).getTime(); 
  const forcedMs = new Date(f.forcedCloseAt).getTime();

  if (!f.name.trim()) errs.name = 'RFQ name is required'; 
  if (f.referenceId && !/^[A-Za-z0-9_-]{2,40}$/.test(f.referenceId)) errs.referenceId = '2-40 chars: letters, digits, - or _'; 
  if (!f.bidStartAt) errs.bidStartAt = 'Required';
  if (!f.bidCloseAt) errs.bidCloseAt = 'Required';
  else if (closeMs <= startMs) errs.bidCloseAt = 'Must be after bid start'; //
  else if (closeMs <= Date.now()) errs.bidCloseAt = 'Must be in the future'; 
  if (!f.forcedCloseAt) errs.forcedCloseAt = 'Required';
  else if (forcedMs <= closeMs) errs.forcedCloseAt = 'Must be later than bid close time'; //hard stop last??
  if (!f.pickupDate) errs.pickupDate = 'Required';
  const x = Number(f.triggerWindowMinutes); //parse window!
  const y = Number(f.extensionMinutes); //parse extension!
  if (!Number.isInteger(x) || x < 1 || x > 1440) errs.triggerWindowMinutes = 'Whole minutes, 1-1440'; 
  if (!Number.isInteger(y) || y < 1 || y > 1440) errs.extensionMinutes = 'Whole minutes, 1-1440'; 
  return errs;
}

function FormRow({ label, err, hint, children }) { // reusable row
  return (
    <label className={`field ${err ? 'has-error' : ''}`}> {/* highlight error */}
      <span className="label">{label}</span>
      {children}
      {err ? <span className="error">{err}</span> : hint && <span className="hint">{hint}</span>} {/* err or hint */}
    </label>
  );
}

export default function CreateRfq() {
  const [form, setForm] = useState(getInitialForm); //form state!!
  const [errs, setErrs] = useState({}); //field errors
  const [submitErr, setSubmitErr] = useState(null); //top error!
  const [saving, setSaving] = useState(false); //loading guard?
  const navigate = useNavigate(); 

  const setField = (key) => (ev) => setForm((f) => ({ ...f, [key]: ev.target.value })); //field updater!!

  async function onSubmit(ev) {
    ev.preventDefault(); //no refresh.
    const validationErrs = validateForm(form); //validate first
    setErrs(validationErrs);
    setSubmitErr(null); //clear old
    if (Object.keys(validationErrs).length > 0) return; //bail early!

    setSaving(true); //lock it!!
    try {
      const { rfq } = await api.createRfq({ //fire away???
        ...form,
        referenceId: form.referenceId || undefined, //optional field/
        bidStartAt: new Date(form.bidStartAt).toISOString(), //to UTC.
        bidCloseAt: new Date(form.bidCloseAt).toISOString(), 
        forcedCloseAt: new Date(form.forcedCloseAt).toISOString(), 
        triggerWindowMinutes: Number(form.triggerWindowMinutes), 
        extensionMinutes: Number(form.extensionMinutes), 
      });
      navigate(`/rfqs/${rfq.id}`); 
    } catch (e) {
      setErrs(e.details || {}); //field errors
      setSubmitErr(e.message); //top message
    } finally {
      setSaving(false); //unlock form!
    }
  }

  const xVal = form.triggerWindowMinutes || 'X'; //preview X
  const yVal = form.extensionMinutes || 'Y'; //preview Y

  return (
    <form className="create-form" onSubmit={onSubmit} noValidate> {/* no browser validation */}
      <div className="page-head">
        <h1>Create RFQ</h1>
        <Link to="/" className="muted">Cancel</Link> {/* bail out */}
      </div>

      {submitErr && <div className="alert alert-error">{submitErr}</div>} {/* top error */}

      <section className="card">
        <h2>RFQ details</h2>
        <div className="grid-2">
          <FormRow label="RFQ name *" err={errs.name}>
            <input value={form.name} onChange={setField('name')} placeholder="Mumbai → Delhi FTL, 20 MT" />
          </FormRow>
          <FormRow label="Reference ID" err={errs.referenceId} hint="Leave blank to auto-generate">
            <input value={form.referenceId} onChange={setField('referenceId')} placeholder="RFQ-2026-001" />
          </FormRow>
          <FormRow label="Pickup / service date *" err={errs.pickupDate}>
            <input type="date" value={form.pickupDate} onChange={setField('pickupDate')} />
          </FormRow>
        </div>
      </section>

      <section className="card">
        <h2>Bid schedule</h2>
        <div className="grid-3">
          <FormRow label="Bid start *" err={errs.bidStartAt}>
            <input type="datetime-local" value={form.bidStartAt} onChange={setField('bidStartAt')} />
          </FormRow>
          <FormRow label="Bid close *" err={errs.bidCloseAt}>
            <input type="datetime-local" value={form.bidCloseAt} onChange={setField('bidCloseAt')} />
          </FormRow>
          <FormRow label="Forced bid close *" err={errs.forcedCloseAt} hint="Hard stop. Must be later than bid close.">
            <input type="datetime-local" value={form.forcedCloseAt} onChange={setField('forcedCloseAt')} />
          </FormRow>
        </div>
      </section>

      <section className="card">
        <h2>British auction configuration</h2>
        <div className="grid-2">
          <FormRow label="Trigger window (X minutes) *" err={errs.triggerWindowMinutes}
            hint={`Watch activity in the last ${xVal} min before close`}>
            <input type="number" min="1" max="1440" value={form.triggerWindowMinutes} onChange={setField('triggerWindowMinutes')} />
          </FormRow>
          <FormRow label="Extension duration (Y minutes) *" err={errs.extensionMinutes}
            hint={`Add ${yVal} min to close time when triggered`}>
            <input type="number" min="1" max="1440" value={form.extensionMinutes} onChange={setField('extensionMinutes')} />
          </FormRow>
        </div>
        <div className="field">
          <span className="label">Extension trigger *</span>
          <div className="radio-group"> {/* pick one */}
            {Object.entries(TRIGGER_LABEL).map(([val, lbl]) => (
              <label key={val} className={`radio ${form.triggerType === val ? 'checked' : ''}`}> {/* highlight selected */}
                <input type="radio" name="triggerType" value={val}
                  checked={form.triggerType === val} onChange={setField('triggerType')} />
                <span>{lbl.replace('X', xVal)}</span>
              </label>
            ))}
          </div>
          {errs.triggerType && <span className="error">{errs.triggerType}</span>} {/* trigger error */}
        </div>
      </section>

      <div className="actions">
        <button className="btn btn-primary" disabled={saving}> {/* disable while saving */}
          {saving ? 'Creating…' : 'Create RFQ'} {/* dynamic label */}
        </button>
      </div>
    </form>
  );
}
