from rest_framework import serializers

from apps.fulfillment.models import Appointment, OrderDelivery, VerifyCode

from .models import Order, OrderItem, OrderStatusLog


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "sku_id",
            "title",
            "price",
            "quantity",
            "amount",
            "refund_amount",
            "snapshot_json",
        )


class OrderDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderDelivery
        fields = (
            "type",
            "address_snapshot",
            "receiver_name",
            "receiver_phone",
            "logistics_company",
            "logistics_no",
            "pickup_code",
            "shipped_at",
            "received_at",
        )


class VerifyCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerifyCode
        fields = ("id", "code", "type", "status", "valid_from", "valid_to", "used_at")


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ("slot_id", "slot_date", "start_time", "end_time", "status", "confirmed_at", "remark")


class OrderStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusLog
        fields = ("from_status", "to_status", "event", "operator_type", "operator_name", "reason", "created_at")


class OrderListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    order_type_label = serializers.CharField(source="get_order_type_display", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_no",
            "merchant_id",
            "merchant_name",
            "order_type",
            "order_type_label",
            "status",
            "status_label",
            "payable_amount",
            "paid_amount",
            "refunded_amount",
            "created_at",
            "paid_at",
            "completed_at",
        )


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    delivery = OrderDeliverySerializer(read_only=True)
    verify_codes = VerifyCodeSerializer(many=True, read_only=True)
    appointment = AppointmentSerializer(read_only=True)
    status_logs = OrderStatusLogSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + (
            "fulfillment_status",
            "product_amount",
            "delivery_fee",
            "commission_rate",
            "commission_amount",
            "contact_json",
            "remark",
            "items",
            "delivery",
            "verify_codes",
            "appointment",
            "status_logs",
        )
