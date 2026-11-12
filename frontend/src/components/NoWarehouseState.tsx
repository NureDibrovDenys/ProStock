// спільне повідомлення, коли поточний склад не визначено

import { useAuth } from '../auth/AuthContext';
import { canSwitchWarehouse } from '../lib/roles';
import { Card, PageHeader } from './ui';
import { WarehouseSwitcher } from './WarehouseSwitcher';
import styles from './NoWarehouseState.module.css';

export function NoWarehouseState() {
  const { session } = useAuth();
  const isAdmin = canSwitchWarehouse(session?.user);

  return (
    <>
      <PageHeader
        title={isAdmin ? 'Склад не обрано' : 'Вас ще не призначено на склад'}
        subtitle={
          isAdmin
            ? 'Оберіть склад — мапа, дашборд і список співробітників перемкнуться на нього.'
            : 'Зверніться до адміністратора для призначення складу.'
        }
      />
      {/* Адміністратор обирає склад просто тут; решта ролей чекає призначення */}
      {isAdmin && (
        <Card className={styles.panel}>
          <WarehouseSwitcher variant="page" />
        </Card>
      )}
    </>
  );
}
