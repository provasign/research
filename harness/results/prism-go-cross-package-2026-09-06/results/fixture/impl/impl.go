package impl
import (
    "example.com/cross/api"
    "example.com/cross/util"
)
type Writer struct{}
func (*Writer) CloseNotify() <-chan bool { return nil }
var _ api.Writer = (*Writer)(nil)
var _ = util.Marker
type Wrong struct{}
func (*Wrong) CloseNotify() chan bool { return nil }
