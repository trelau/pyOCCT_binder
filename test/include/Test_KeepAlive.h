
class Test_Node
{
public:

    Test_Node();

};


class Test_Mesh
{
public:

    Test_Mesh();

    // Dear SMESHd devs, do not use raw pointers like this...
    void AddNode(const int id, Test_Node* node);
};
