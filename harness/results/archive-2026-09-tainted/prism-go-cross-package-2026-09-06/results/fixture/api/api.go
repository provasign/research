package api
import "net/http"
type Writer interface { http.CloseNotifier }
func Stream(w Writer) { <-w.CloseNotify() }
