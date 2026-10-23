
//congifs!

import react from '@vitejs/plugin-react'; //understand &build react/jsx files!!
import { defineConfig } from 'vite'; //autocomplete when writing this config..

export default defineConfig({ //wrapping everything!
  plugins: [react()], //activate the react plugin.
  server: { //dev server settings
    port: 5173, //run the frontend on this port!
    proxy: { '/api': process.env.API_URL || 'http://localhost:8000' }, //forward /api calls to the backend!
  },
});

