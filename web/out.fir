module attributes {dlti.dl_spec = #dlti.dl_spec<#dlti.dl_entry<i64, dense<64> : vector<2xi64>>, #dlti.dl_entry<!llvm.ptr<272>, dense<64> : vector<4xi64>>, #dlti.dl_entry<!llvm.ptr<271>, dense<32> : vector<4xi64>>, #dlti.dl_entry<!llvm.ptr<270>, dense<32> : vector<4xi64>>, #dlti.dl_entry<f128, dense<128> : vector<2xi64>>, #dlti.dl_entry<f64, dense<64> : vector<2xi64>>, #dlti.dl_entry<f16, dense<16> : vector<2xi64>>, #dlti.dl_entry<i32, dense<32> : vector<2xi64>>, #dlti.dl_entry<i16, dense<16> : vector<2xi64>>, #dlti.dl_entry<i8, dense<8> : vector<2xi64>>, #dlti.dl_entry<!llvm.ptr, dense<64> : vector<4xi64>>, #dlti.dl_entry<i1, dense<8> : vector<2xi64>>, #dlti.dl_entry<f80, dense<128> : vector<2xi64>>, #dlti.dl_entry<i128, dense<128> : vector<2xi64>>, #dlti.dl_entry<"dlti.endianness", "little">, #dlti.dl_entry<"dlti.stack_alignment", 128 : i64>>, fir.defaultkind = "a1c4d8i4l4r4", fir.kindmap = "", llvm.data_layout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128", llvm.target_triple = "x86_64-pc-linux-gnu"} {
  func.func @_QQmain() attributes {fir.bindc_name = "test"} {
    %0 = fir.alloca f32 {bindc_name = "a", uniq_name = "_QFEa"}
    %1 = fir.declare %0 {uniq_name = "_QFEa"} : (!fir.ref<f32>) -> !fir.ref<f32>
    %2 = fir.alloca f32 {bindc_name = "b", uniq_name = "_QFEb"}
    %3 = fir.declare %2 {uniq_name = "_QFEb"} : (!fir.ref<f32>) -> !fir.ref<f32>
    %4 = fir.alloca f32 {bindc_name = "c", uniq_name = "_QFEc"}
    %5 = fir.declare %4 {uniq_name = "_QFEc"} : (!fir.ref<f32>) -> !fir.ref<f32>
    %6 = fir.load %1 : !fir.ref<f32>
    %7 = fir.load %3 : !fir.ref<f32>
    %8 = arith.addf %6, %7 fastmath<contract> : f32
    fir.store %8 to %5 : !fir.ref<f32>
    return
  }
  fir.global @_QQEnvironmentDefaults constant : !fir.ref<tuple<i32, !fir.ref<!fir.array<0xtuple<!fir.ref<i8>, !fir.ref<i8>>>>>> {
    %0 = fir.zero_bits !fir.ref<tuple<i32, !fir.ref<!fir.array<0xtuple<!fir.ref<i8>, !fir.ref<i8>>>>>>
    fir.has_value %0 : !fir.ref<tuple<i32, !fir.ref<!fir.array<0xtuple<!fir.ref<i8>, !fir.ref<i8>>>>>>
  }
}
