import { Navigate, Route, Routes } from 'react-router-dom';
import { AUTH_ENABLED } from './config';
import { RequireAuth } from './auth/RequireAuth';
import { AppLayout } from './components/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { EmployeesPage } from './pages/EmployeesPage';
import { LoginPage } from './pages/LoginPage';
import { MapEditorPage } from './pages/MapEditorPage';
import { NewEmployeePage } from './pages/NewEmployeePage';
import { RackPage } from './pages/RackPage';
import { WarehousePage } from './pages/WarehousePage';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={AUTH_ENABLED ? <LoginPage /> : <Navigate to="/" replace />} />
      <Route element={<RequireAuth />}>
        {/* Редактор мапи — повноекранний, без навбару (як у макеті) */}
        <Route path="/warehouse/edit" element={<MapEditorPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/employees/new" element={<NewEmployeePage />} />
          <Route path="/warehouse" element={<WarehousePage />} />
          <Route path="/warehouse/racks/:rackCode" element={<RackPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
