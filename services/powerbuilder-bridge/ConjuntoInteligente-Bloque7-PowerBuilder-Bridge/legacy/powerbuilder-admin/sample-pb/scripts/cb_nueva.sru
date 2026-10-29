$PBExportHeader$cb_nueva.sru
forward
global type cb_nueva from commandbutton within w_orders
end type
global type cb_nueva from commandbutton
integer x=530
integer y=20
integer width=500
integer height=130
string text="Nueva orden"
end type
event clicked;
 MessageBox("Próximamente","El formulario de creación se implementa en la siguiente iteración del puente, una vez validado el flujo de solo lectura.")
end event
on cb_nueva.create
 call super::create
 TriggerEvent(this,"constructor")
end on
on cb_nueva.destroy
 TriggerEvent(this,"destructor")
 call super::destroy
end on
