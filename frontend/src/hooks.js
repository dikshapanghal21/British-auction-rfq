//..

import { useEffect, useRef, useState } from 'react'; 
import { serverNow } from './api.js'; //synced clock!

export function usePolling(fetcher, ms = 3000) { 
  const [data, setData] = useState(null); //fetch data
  const [err, setErr] = useState(null); 
  const latestFetcher = useRef(fetcher); // avoid stale closure?
  latestFetcher.current = fetcher;

  function doFetch() { //fire request
    latestFetcher.current()
      .then(d => { setData(d); setErr(null); }) 
      .catch(e => setErr(e)); 
  }

  useEffect(() => {
    doFetch(); //fetch immediately
    const timer = setInterval(doFetch, ms); //then repeat
    return () => clearInterval(timer); 
  }, [ms]); 

  return { data, err, reload: doFetch }; //expose all.
}

export function useNow() { //live clock!!!
  const [now, setNow] = useState(serverNow()); //start synced
  useEffect(() => {
    const timer = setInterval(() => setNow(serverNow()), 1000); 
    return () => clearInterval(timer); 
  }, []);
  return now; //current time returned!
}


