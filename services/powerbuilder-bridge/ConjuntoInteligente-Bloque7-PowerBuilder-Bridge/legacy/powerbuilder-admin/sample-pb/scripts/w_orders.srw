$PBExportHeader$w_orders.srw
forward
global type w_orders from window
end type
type cb_refresh from commandbutton within w_orders
end type
type dw_orders from datawindow within w_orders
end type
type cb_nueva from commandbutton within w_orders
end type
type variables
 nvo_api_client inv_client
 nvo_orders inv_orders
end variables
global type w_orders from window
integer width=3200
integer height=2000
boolean titlebar=true
string title="Órdenes — Conjunto Inteligente"
boolean controlmenu=true
boolean minbox=true
boolean maxbox=true
boolean resizable=true
long backcolor=15921906
string icon="AppIcon!"
boolean center=true
event open
event closequery
end type
global w_orders w_orders
on w_orders.create
 this.cb_refresh=create cb_refresh
 this.dw_orders=create dw_orders
 this.cb_nueva=create cb_nueva
 call super::create
 TriggerEvent(this,"constructor")
end on
on w_orders.destroy
 TriggerEvent(this,"destructor")
 destroy this.cb_nueva
 destroy this.dw_orders
 destroy this.cb_refresh
 call super::destroy
end on
event constructor;
 inv_client=create nvo_api_client
 inv_orders=create nvo_orders
 inv_client.of_set_config("http://localhost:5100","dev-token-not-for-production-0000",10000)
 inv_orders.of_attach_client(inv_client)
end event
event open;
 this.event ue_refresh()
end event
event ue_refresh;
 string ls_json
 long ll_rowcount
 SetPointer(HourGlass!)
 ls_json=inv_orders.of_list("","","")
 ll_rowcount=dw_orders.ImportString(JSON!,ls_json,false)
 if ll_rowcount<0 then MessageBox("Error","No se pudieron cargar las órdenes: "+inv_client.of_parse_error(ls_json))
 SetPointer(Arrow!)
end event
event closequery;
 destroy inv_orders
 destroy inv_client
 return 0
end event
