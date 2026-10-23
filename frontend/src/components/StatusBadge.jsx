//..

import { STATUS_LABEL } from '../format.js'; //label themap


export default function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status.toLowerCase()}`}> {/* dynamic styling */}
      {STATUS_LABEL[status] ?? status} {/* fallback raw */}
    </span>
  );
}


