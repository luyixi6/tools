import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ConfigPage from './pages/ConfigPage'
import ScanPage from './pages/ScanPage'
import AnalysisPage from './pages/AnalysisPage'
import ResultsPage from './pages/ResultsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ConfigPage />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/analysis/:scanId" element={<AnalysisPage />} />
          <Route path="/results/:scanId" element={<ResultsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
