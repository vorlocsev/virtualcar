package main

import (
	"strings"
	"testing"
)

func TestCoreBridgeAssessment(t *testing.T) {
	cases := []struct {
		name, input      string
		enabled          bool
		count, fb, wrong int
	}{
		{"dev26", "{\"schema\":15,\"core_version\":26,\"event\":\"connect\"}\n{\"schema\":15,\"core_version\":26,\"event\":\"write\",\"status\":0,\"count\":1,\"core_class\":\"a3_0203_shape\",\"core_decision\":2}\n{\"schema\":15,\"core_version\":26,\"event\":\"write\",\"status\":0,\"count\":1,\"core_class\":\"b9fb_existing\",\"core_decision\":0}\n{\"schema\":15,\"core_version\":26,\"event\":\"write\",\"status\":0,\"count\":1,\"core_class\":\"a3_0203_shape\",\"core_decision\":1}\n", true, 3, 1, 1},
		{"legacy", "{\"schema\":15,\"event\":\"write\",\"status\":0,\"count\":1,\"class\":\"a3_tx\"}\n", false, 0, 0, 0},
		{"failed_tx", "{\"schema\":15,\"core_version\":26,\"event\":\"write\",\"status\":7,\"count\":0,\"core_class\":\"b9fb_existing\"}\n", true, 0, 0, 0},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			v, e := readCoreBridgeAssessment([]byte(tt.input))
			if e != nil {
				t.Fatal(e)
			}
			if v.Enabled != tt.enabled || v.InspectedD2TX != tt.count || v.B9FBDelegated != tt.fb || v.RouteMismatchAnnotations != tt.wrong {
				t.Fatalf("got %+v", v)
			}
		})
	}
	_, err := readCoreBridgeAssessment([]byte("not json"))
	if err == nil {
		t.Fatal("invalid input accepted")
	}
	_, err = readCoreBridgeAssessment([]byte(strings.Repeat("x", 2*1024*1024)))
	if err == nil {
		t.Fatal("oversized line accepted")
	}
}
