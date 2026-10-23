//..

import React from 'react'; 
import ReactDOM from 'react-dom/client'; //mounts app!
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'; 
import AuctionDetail from './pages/AuctionDetail.jsx'; //detail page
import AuctionList from './pages/AuctionList.jsx'; //list page
import CreateRfq from './pages/CreateRfq.jsx'; //create page
import './styles.css';


function App() {
  return (
    <BrowserRouter> {/* wrap everything */}
      <header className="topbar">
        <Link to="/" className="brand">RFQ · British Auction</Link> {/* home link */}
        <Link to="/rfqs/new" className="btn btn-primary">+ New RFQ</Link> {/* create button */}
      </header>
      <main className="container">
        <Routes> {/* pick a route */}
          <Route path="/" element={<AuctionList />} /> {/* home page */}
          <Route path="/rfqs/new" element={<CreateRfq />} /> {/* create page */}
          <Route path="/rfqs/:id" element={<AuctionDetail />} /> {/* detail page */}
          <Route path="*" element={<p>Page not found. <Link to="/">Back to auctions</Link></p>} /> {/* 404 catch */}
        </Routes>
      </main>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render( //mount it!!!
  <React.StrictMode><App /></React.StrictMode> //strict mode?
);


