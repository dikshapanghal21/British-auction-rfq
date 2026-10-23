//..

const inr0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }); //no decimals
const inr2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }); //paise

export function money(n) {  //rupee formatter
  if (n == null) return '—'; 
  return Number.isInteger(n) ? inr0.format(n) : inr2.format(n); 
}


export function dateTime(iso) {  //date + time
  if (!iso) return '—';  
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}


export function clock(iso) { //time only!!
  return new Date(iso).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function timeWithSeconds(iso) { //full timestamp...
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function dateOnly(ymd) { //date  
  if (!ymd) return '—'; 
  return new Date(`${ymd}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

export function countdown(ms) { 
  if (ms <= 0) return '00:00'; 
  const totalSec = Math.floor(ms / 1000); //to seconds
  const days = Math.floor(totalSec / 86400); //days left
  const hrs = Math.floor((totalSec % 86400) / 3600); //hrs left
  const mins = Math.floor((totalSec % 3600) / 60); //mins left
  const secs = totalSec % 60; //secs left
  const pad = (n) => String(n).padStart(2, '0');
  const hms = (hrs || days) ? `${pad(hrs)}:${pad(mins)}:${pad(secs)}` : `${pad(mins)}:${pad(secs)}`; 
  return days ? `${days}d ${hms}` : hms; //prepend days
}

export const STATUS_LABEL = { //labels/
  UPCOMING: 'Upcoming',
  ACTIVE: 'Active',
  CLOSED: 'Closed',
  FORCE_CLOSED: 'Force Closed',
};

export const TRIGGER_LABEL = { //trigger labels!!
  BID_RECEIVED: 'Bid received in last X minutes',
  ANY_RANK_CHANGE: 'Any supplier rank change in last X minutes',
  L1_CHANGE: 'Lowest bidder (L1) change in last X minutes',
};

export function toLocalInput(ms) { //datetime-local value
  const d = new Date(ms);
  d.setSeconds(0, 0); 
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); //strip timezone
}

export function toLocalDateInput(ms) { 
  return toLocalInput(ms).slice(0, 10); // 
}


