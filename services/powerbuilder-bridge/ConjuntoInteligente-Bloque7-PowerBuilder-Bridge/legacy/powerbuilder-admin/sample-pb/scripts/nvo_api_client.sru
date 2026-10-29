$PBExportHeader$nvo_api_client.sru
forward
global type nvo_api_client from nonvisualobject
end type
type variables
 string is_base_url
 string is_service_token
 long il_timeout_ms
 boolean ib_debug
end variables
forward prototypes
public subroutine of_set_config (string as_base_url, string as_token, long al_timeout_ms)
public function boolean of_health ()
public function string of_get (string as_path)
public function string of_post (string as_path, string as_body)
public function string of_parse_error (string as_response)
end prototypes
public subroutine of_set_config (string as_base_url,string as_token,long al_timeout_ms); is_base_url=as_base_url; is_service_token=as_token; il_timeout_ms=al_timeout_ms; ib_debug=false
end subroutine
public function boolean of_health (); string ls_response; long ll_status; ls_response=of_get_with_status("/health",ll_status); return (ll_status=200); end function
public function string of_get (string as_path); long ll_status; return of_get_with_status(as_path,ll_status); end function
public function string of_post (string as_path,string as_body); long ll_status; return of_post_with_status(as_path,as_body,ll_status); end function
public function string of_get_with_status (string as_path,ref long al_status); System.Net.Http.HttpClient lnv_client; System.Net.Http.HttpResponseMessage lnv_resp; System.Net.Http.Headers.AuthenticationHeaderValue lnv_auth; System.Net.Http.HttpRequestMessage lnv_req; string ls_url; string ls_body=""; try ls_url=is_base_url+as_path; lnv_client=create System.Net.Http.HttpClient; lnv_client.Timeout=System.TimeSpan.FromMilliseconds(il_timeout_ms); lnv_auth=create System.Net.Http.Headers.AuthenticationHeaderValue & ("Bearer",is_service_token); lnv_client.DefaultRequestHeaders.Authorization=lnv_auth; lnv_client.DefaultRequestHeaders.Add("X-PB-Service-Token",is_service_token); lnv_client.DefaultRequestHeaders.Add("Accept","application/json"); lnv_req=create System.Net.Http.HttpRequestMessage & (System.Net.Http.HttpMethod.Get,ls_url); lnv_resp=lnv_client.SendAsync(lnv_req).Result; al_status=integer(lnv_resp.StatusCode); ls_body=lnv_resp.Content.ReadAsStringAsync().Result; if ib_debug then MessageBox("PB Bridge GET",ls_url+"~r~n~r~n"+ls_body); end if; destroy lnv_req; destroy lnv_resp; destroy lnv_client; catch (System.Exception ex) al_status=-1; ls_body='{"ok":false,"code":"PB_CLIENT_ERROR","message":"'+ex.Message+'"}'; if ib_debug then MessageBox("PB Bridge Error",ex.Message); end if; end try; return ls_body; end function
public function string of_post_with_status (string as_path,string as_body,ref long al_status); System.Net.Http.HttpClient lnv_client; System.Net.Http.HttpResponseMessage lnv_resp; System.Net.Http.StringContent lnv_content; System.Net.Http.Headers.AuthenticationHeaderValue lnv_auth; string ls_url; string ls_response=""; try ls_url=is_base_url+as_path; lnv_client=create System.Net.Http.HttpClient; lnv_client.Timeout=System.TimeSpan.FromMilliseconds(il_timeout_ms); lnv_auth=create System.Net.Http.Headers.AuthenticationHeaderValue & ("Bearer",is_service_token); lnv_client.DefaultRequestHeaders.Authorization=lnv_auth; lnv_client.DefaultRequestHeaders.Add("X-PB-Service-Token",is_service_token); lnv_client.DefaultRequestHeaders.Add("Accept","application/json"); lnv_content=create System.Net.Http.StringContent & (as_body,System.Text.Encoding.UTF8,"application/json"); lnv_resp=lnv_client.PostAsync(ls_url,lnv_content).Result; al_status=integer(lnv_resp.StatusCode); ls_response=lnv_resp.Content.ReadAsStringAsync().Result; if ib_debug then MessageBox("PB Bridge POST",ls_url+"~r~n~r~n"+ls_response); end if; destroy lnv_content; destroy lnv_resp; destroy lnv_client; catch (System.Exception ex) al_status=-1; ls_response='{"ok":false,"code":"PB_CLIENT_ERROR","message":"'+ex.Message+'"}'; if ib_debug then MessageBox("PB Bridge Error",ex.Message); end if; end try; return ls_response; end function
public function string of_parse_error (string as_response); long ll_pos_start,ll_pos_end; string ls_message; ll_pos_start=Pos(as_response,'"message":"'); if ll_pos_start=0 then return "Error desconocido"; ll_pos_start=ll_pos_start+11; ll_pos_end=Pos(as_response,'"',ll_pos_start); if ll_pos_end=0 then return "Error desconocido"; ls_message=Mid(as_response,ll_pos_start,ll_pos_end-ll_pos_start); return ls_message; end function
on nvo_api_client.create
 call super::create
end on
on nvo_api_client.destroy
 call super::destroy
end on
