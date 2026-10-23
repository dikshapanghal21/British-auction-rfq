//track the difference between server clock and browser clock
let clockOffset = 0; //drift thetracker

export function serverNow() {
  return Date.now() + clockOffset; //adjusted time
}

export class ApiError extends Error { //custom error
  constructor(status, message, details) {
    super(message);
    this.status = status; //http code//
    this.details = details || {}; //field errors!
  }
}

async function request(path, options = {}) { //base fetcher!
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' }, 
    ...options,
  });
  const body = await res.json().catch(() => ({})); //parse
  if (!res.ok) {
    throw new ApiError(res.status, body.error || `Request failed (${res.status})`, body.details); //blow up!!!
  }
  if (body.serverTime) {
    clockOffset = new Date(body.serverTime).getTime() - Date.now(); //syncclocks
  }
  return body;
}

export const api = {
  listRfqs: () => request('/rfqs'),  //get all
  getRfq: (id) => request(`/rfqs/${id}`), //get one
  createRfq: (data) => request('/rfqs', { method: 'POST', body: JSON.stringify(data) }), //make 1
  submitBid: (id, data) => request(`/rfqs/${id}/bids`, { method: 'POST', body: JSON.stringify(data) }), //place the bid!!
};


