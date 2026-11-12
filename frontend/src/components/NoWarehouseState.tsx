// спільне повідомлення

import { useAuth } from "../auth/AuthContext";
import { PageHeader } from "./ui";

export function NoWarehouseState(){
    const {session} = useAuth();

    const isAdmin = 
    session?.user.role === "administrator" ||
    session?.user.role === "root";

    return(
        <PageHeader
        title = {isAdmin ? 'Склад не обрано' : 'Вас ще не призначено на склад'}
        subtitle={
        isAdmin
          ? 'Керування співробітниками доступне в розділі «Співробітники».'
          : 'Зверніться до адміністратора для призначення складу.'
      }
      />
    )
}