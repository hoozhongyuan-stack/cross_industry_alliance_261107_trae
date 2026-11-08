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


class CartItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    sku_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class CartItemPatchSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=99, required=False)
    selected = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("至少提供一个可修改字段")
        return attrs


class CartItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    merchant_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    sku_id = serializers.IntegerField(allow_null=True)
    title = serializers.CharField()
    cover_url = serializers.CharField()
    spec = serializers.DictField()
    price_amount = serializers.IntegerField()
    quantity = serializers.IntegerField()
    selected = serializers.BooleanField()
    available_stock = serializers.IntegerField(allow_null=True)


class CartSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField(allow_null=True)
    items = CartItemSerializer(many=True)
    total_amount = serializers.IntegerField()


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    sku_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class ContactInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    phone = serializers.CharField(max_length=20)
    address_id = serializers.IntegerField(required=False, allow_null=True)
    address_detail = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class AppointmentInputSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)
    remark = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class OrderCreateInputSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField(min_value=1)
    order_type = serializers.ChoiceField(choices=["EXPRESS", "PICKUP", "SERVICE"])
    items = OrderItemInputSerializer(many=True, allow_empty=False)
    contact = ContactInputSerializer()
    appointment = AppointmentInputSerializer(required=False, allow_null=True)
    remark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class PayInputSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["WECHAT_MINI", "WECHAT_H5"], default="WECHAT_MINI")


class CancelInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class OrderItemContractSerializer(serializers.ModelSerializer):
    price_amount = serializers.IntegerField(source="price")
    amount = serializers.IntegerField()
    refund_amount = serializers.IntegerField()

    class Meta:
        model = OrderItem
        fields = ("id", "product_id", "sku_id", "title", "price_amount", "quantity", "amount", "refund_amount")


class OrderContractSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    contact = serializers.JSONField(source="contact_json")
    items = OrderItemContractSerializer(many=True, read_only=True)
    verify_codes = VerifyCodeSerializer(many=True, read_only=True)
    appointment = AppointmentSerializer(read_only=True)
    delivery = OrderDeliverySerializer(read_only=True)
    timeline = OrderStatusLogSerializer(source="status_logs", many=True, read_only=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=4, coerce_to_string=False)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_no",
            "merchant_id",
            "merchant_name",
            "order_type",
            "status",
            "fulfillment_status",
            "product_amount",
            "delivery_fee",
            "payable_amount",
            "paid_amount",
            "refunded_amount",
            "commission_rate",
            "commission_amount",
            "contact",
            "remark",
            "items",
            "verify_codes",
            "appointment",
            "delivery",
            "timeline",
            "expire_at",
            "paid_at",
            "completed_at",
            "created_at",
        )
