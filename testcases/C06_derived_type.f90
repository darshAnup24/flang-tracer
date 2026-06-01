! C06: Derived type with allocatable
program derived_allocatable
    implicit none
    type node
        integer, allocatable :: data(:)
    end type node
    type(node) :: my_node
    
    ! The construct below will be traced
    allocate(my_node%data(10))
    my_node%data = 42
end program derived_allocatable
