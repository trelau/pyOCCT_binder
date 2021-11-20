
class Test_Getter
{
public:

    Test_Getter();

    // Should use default policy
    int& OtherValue();

    // Should apply reference_internal policy
    int& Value();
    SetValue(int v);

};

