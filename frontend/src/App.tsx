import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth } from './auth/RequireAuth';
import { RequirePermission } from './auth/RequirePermission';
import { AppLayout } from './components/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { EmployeesPage } from './pages/EmployeesPage';
import { LoginPage } from './pages/LoginPage';
import { MapEditorPage } from './pages/MapEditorPage';
import { NewEmployeePage } from './pages/NewEmployeePage';
import { ProductsPage } from './pages/ProductsPage';
import { RackPage } from './pages/RackPage';
import { WarehousePage } from './pages/WarehousePage';
import { AUTH_ENABLED } from './config';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={AUTH_ENABLED ? <LoginPage /> : <Navigate to="/" replace />} />
      <Route element={<RequireAuth />}>
        {/* Редактор мапи — повноекранний, без навбару (як у макеті) */}
        <Route path="/warehouse/edit" element={<MapEditorPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/products" replace />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route
            path="/employees"
            element={
              <RequirePermission permission="users_manage">
                <EmployeesPage />
              </RequirePermission>
            }
          />
          <Route
            path="/employees/new"
            element={
              <RequirePermission permission="users_manage">
                <NewEmployeePage />
              </RequirePermission>
            }
          />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/warehouse" element={<WarehousePage />} />
          <Route path="/warehouse/racks/:rackCode" element={<RackPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
