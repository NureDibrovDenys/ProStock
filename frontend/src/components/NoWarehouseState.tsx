// спільне повідомлення

import { isAdminRole } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import { useWarehouses } from "../hooks/useCurrentWarehouse";
import { Button } from "./Button";
import { ErrorState, LoadingState, PageHeader } from "./ui";

export function NoWarehouseState(){
    const {session} = useAuth();

    // Адміністратор бачить це лише тоді, коли складів ще немає взагалі
    const isAdmin = isAdminRole(session?.user.role);
    const warehouses = useWarehouses(isAdmin);

    if (isAdmin && warehouses.isPending) return <LoadingState />;
    if (isAdmin && warehouses.isError) return <ErrorState error={warehouses.error} onRetry={() => warehouses.refetch()} />;

    return(
        <PageHeader
        title = {isAdmin ? 'Складів ще немає' : 'Вас ще не призначено на склад'}
        subtitle={
        isAdmin
          ? 'Створіть склад у розділі «Склади» — після цього тут з’являться його дані.'
          : 'Зверніться до адміністратора для призначення складу.'
      }
        actions={isAdmin ? <Button to="/warehouses">Перейти до складів</Button> : undefined}
      />
    )
}
