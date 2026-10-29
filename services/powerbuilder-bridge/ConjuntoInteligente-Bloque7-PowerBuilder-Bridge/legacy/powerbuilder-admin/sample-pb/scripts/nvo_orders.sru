$PBExportHeader$nvo_orders.sru
forward
global type nvo_orders from nonvisualobject
end type
type variables
 nvo_api_client inv_client
end variables
forward prototypes
public subroutine of_attach_client (nvo_api_client anv_client)
public function string of_list (string as_estado, string as_categoria, string as_busqueda)
public function string of_detail (string as_order_id)
end prototypes
public subroutine of_attach_client (nvo_api_client anv_client); inv_client=anv_client; end subroutine
public function string of_list (string as_estado,string as_categoria,string as_busqueda); string ls_body; string ls_json; ls_body='{"estado":"'+as_estado+'","categoria":"'+as_categoria+'","busqueda":"'+as_busqueda+'","pagina":1,"porPagina":100}'; ls_json=inv_client.of_post("/pb/v1/orders/list",ls_body); return ls_json; end function
public function string of_detail (string as_order_id); return inv_client.of_get("/pb/v1/orders/"+as_order_id); end function
on nvo_orders.create
 call super::create
end on
on nvo_orders.destroy
 call super::destroy
end on
