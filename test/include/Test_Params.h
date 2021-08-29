#include <vector>

class Test_Item
{
public:
        Test_Item();
};

class Test_Params
{
public:

    Test_Params();

    void AddItems(const std::vector<const Test_Item*>& items) const {};
    void AddItems(const std::vector<const Test_Item*>& items, const std::vector<int>& indices) const {};

};
