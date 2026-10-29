$PBExportHeader$cb_refresh.sru
forward
global type cb_refresh from commandbutton within w_orders
end type
global type cb_refresh from commandbutton
integer x=20
integer y=20
integer width=500
integer height=130
string text="Actualizar"
end type
event clicked;
 parent.event ue_refresh()
end event
on cb_refresh.create
 call super::create
 TriggerEvent(this,"constructor")
end on
on cb_refresh.destroy
 TriggerEvent(this,"destructor")
 call super::destroy
end on
